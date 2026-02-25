from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import (
    SESSION_COOKIE_NAME,
    create_session,
    destroy_session,
    get_current_customer_email,
    require_customer,
    require_superuser,
)
from app.channel_store import channel_store
from app.llm_agent import get_chat_response, get_support_response
from app.models import (
    ChannelCreate,
    ChannelResponse,
    SendMessageRequest,
    TicketCreate,
    TicketResponse,
    TicketUpdateRequest,
    UpdateTicketStatusRequest,
)
from app.ticket_store import store
from app.user_store import (
    delete_user as user_store_delete,
    list_all as user_list_all,
    register as register_user,
    verify as verify_user,
)

app = FastAPI(
    title="Customer Support AI Agent",
    description="Create tickets and get AI-powered responses",
    version="1.0.0",
)


@app.on_event("startup")
async def bootstrap_superusers():
    """Create superuser accounts that don't exist yet when ADMIN_BOOTSTRAP_PASSWORD is set."""
    from app.config import ADMIN_BOOTSTRAP_PASSWORD, SUPERUSER_EMAILS
    if not ADMIN_BOOTSTRAP_PASSWORD or not SUPERUSER_EMAILS:
        return
    for email in SUPERUSER_EMAILS:
        try:
            register_user(email, ADMIN_BOOTSTRAP_PASSWORD)
        except Exception:
            pass  # already exists or store error; ignore


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, _exc):
    return JSONResponse(
        status_code=405,
        content={"detail": "This URL does not support the HTTP method you used. Use POST /tickets to create a ticket."},
    )


# Serve static files if present
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the support portal UI."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return """
    <html>
        <head><title>Support</title></head>
        <body>
            <h1>Customer Support AI</h1>
            <p>Use the API: POST /tickets to create a ticket, GET /tickets/{id} to get the AI response.</p>
        </body>
    </html>
    """


@app.post("/tickets", response_model=TicketResponse)
async def create_ticket(data: TicketCreate):
    """Create a new support ticket and generate an AI response."""
    try:
        ticket = store.create(data)
        ai_response = get_support_response(
            ticket.subject, ticket.description, ticket.customer_email
        )
        store.update_ai_response(ticket.id, ai_response)
        t = store.get(ticket.id)
        if not t:
            raise HTTPException(status_code=500, detail="Failed to retrieve created ticket")
        return TicketResponse(
            ticket_id=t.id,
            subject=t.subject,
            description=t.description,
            status=t.status,
            ai_response=t.ai_response or "",
            created_at=t.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e) if str(e) else "Failed to create ticket or generate AI response",
        )


@app.get("/tickets")
async def list_tickets():
    """List all tickets (for admin/demo)."""
    tickets = store.list_all()
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "status": t.status.value,
            "created_at": t.created_at.isoformat(),
        }
        for t in tickets
    ]


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    """Get a ticket by ID including its AI response."""
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketResponse(
        ticket_id=ticket.id,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        ai_response=ticket.ai_response or "",
        created_at=ticket.created_at,
    )


# --- Customer login & dashboard ---

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Serve the customer login page."""
    html_path = Path(__file__).parent / "templates" / "login.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Login template not found")


@app.post("/login")
async def login(
    customer_email: str = Form(..., alias="customer_email"),
    password: str = Form(...),
):
    """Log in with email and password; set session cookie and redirect to dashboard."""
    email = customer_email.strip().lower()
    if not verify_user(email, password):
        html_path = Path(__file__).parent / "templates" / "login.html"
        if html_path.exists():
            html = html_path.read_text(encoding="utf-8")
            # Inject error message for display
            err = "Invalid email or password. Please try again or <a href=\"/register\">create an account</a>."
            if "id=\"error\"" in html:
                html = html.replace(
                    "<div class=\"error-box\" id=\"error\"></div>",
                    f"<div class=\"error-box visible\" id=\"error\">{err}</div>",
                )
            return HTMLResponse(content=html, status_code=401)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    session_id = create_session(email)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    """Serve the customer registration page."""
    html_path = Path(__file__).parent / "templates" / "register.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Register template not found")


def _register_page_with_error(html_path: Path, err: str) -> HTMLResponse:
    """Render register page with error message."""
    err_div = "<div class=\"error-box\" id=\"error\"></div>"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        html = html.replace(
            err_div,
            f"<div class=\"error-box visible\" id=\"error\">{err}</div>",
        )
        return HTMLResponse(content=html, status_code=400)
    raise HTTPException(status_code=400, detail=err)


@app.post("/register")
async def register(
    customer_email: str = Form(..., alias="customer_email"),
    password: str = Form(...),
):
    """Create an account; redirect to dashboard after auto-login."""
    email = customer_email.strip().lower()
    html_path = Path(__file__).parent / "templates" / "register.html"

    if len(password) < 8:
        return _register_page_with_error(
            html_path, "Password must be at least 8 characters."
        )
    try:
        if not register_user(email, password):
            return _register_page_with_error(
                html_path,
                "This email is already registered. <a href=\"/login\">Log in</a> instead.",
            )
        session_id = create_session(email)
    except Exception as e:
        err_msg = str(e) if str(e) else "Registration or sign-in failed. If you use Supabase, check that the users and sessions tables exist and that Row Level Security allows inserts with your anon key."
        return _register_page_with_error(html_path, err_msg)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return response


@app.post("/logout")
async def logout(request: Request):
    """Clear session and redirect to login."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    destroy_session(session_id)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(email: Optional[str] = Depends(get_current_customer_email)):
    """Serve the customer dashboard (my tickets). Redirect to login if not authenticated."""
    if not email:
        return RedirectResponse(url="/login", status_code=302)
    html_path = Path(__file__).parent / "templates" / "dashboard.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Dashboard template not found")


@app.get("/api/me/tickets")
async def my_tickets(email: str = Depends(require_customer)):
    """List tickets for the logged-in customer."""
    tickets = store.list_by_email(email)
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "status": t.status.value,
            "created_at": t.created_at.isoformat(),
        }
        for t in tickets
    ]


@app.get("/api/me/tickets/{ticket_id}", response_model=TicketResponse)
async def my_ticket_detail(ticket_id: str, email: str = Depends(require_customer)):
    """Get a ticket detail for the logged-in customer (only their tickets)."""
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.customer_email.lower() != email.lower():
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketResponse(
        ticket_id=ticket.id,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        ai_response=ticket.ai_response or "",
        created_at=ticket.created_at,
    )


@app.patch("/api/me/tickets/{ticket_id}/status")
async def update_my_ticket_status(
    ticket_id: str,
    body: UpdateTicketStatusRequest,
    email: str = Depends(require_customer),
):
    """Update ticket status (e.g. mark resolved) for the logged-in customer."""
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.customer_email.lower() != email.lower():
        raise HTTPException(status_code=404, detail="Ticket not found")
    updated = store.update_status(ticket_id, body.status)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update ticket")
    return {
        "ticket_id": updated.id,
        "status": updated.status.value,
    }


# --- Customer chat channel ---

@app.get("/channels")
async def list_channels():
    """List all chat channels (for admin/demo)."""
    channels = channel_store.list_all()
    return [
        {
            "id": c.id,
            "customer_email": c.customer_email,
            "subject": c.subject,
            "message_count": len(c.messages),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in channels
    ]


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """Serve the customer chat channel UI."""
    html_path = Path(__file__).parent / "templates" / "chat.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Chat template not found")


@app.post("/channels", response_model=ChannelResponse)
async def create_channel(data: ChannelCreate):
    """Create a new chat channel. Optionally send an initial message and get AI reply."""
    channel = channel_store.create(data)
    if data.initial_message:
        messages_for_llm = [{"role": "user", "content": data.initial_message.strip()}]
        ai_reply = get_chat_response(
            messages_for_llm,
            channel.customer_email,
            channel.subject,
        )
        channel_store.add_message(channel.id, "assistant", ai_reply)
    ch = channel_store.get(channel.id)
    if not ch:
        raise HTTPException(status_code=500, detail="Failed to retrieve created channel")
    return ChannelResponse(
        channel_id=ch.id,
        customer_email=ch.customer_email,
        subject=ch.subject,
        messages=ch.messages,
        created_at=ch.created_at,
        updated_at=ch.updated_at,
    )


@app.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: str):
    """Get a channel and its message history."""
    channel = channel_store.get(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ChannelResponse(
        channel_id=channel.id,
        customer_email=channel.customer_email,
        subject=channel.subject,
        messages=channel.messages,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@app.post("/channels/{channel_id}/messages")
async def send_message(channel_id: str, body: SendMessageRequest):
    """Send a message in a channel and receive an AI reply."""
    channel = channel_store.get(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel_store.add_message(channel_id, "user", body.content)
    messages_for_llm = [
        {"role": m.role, "content": m.content}
        for m in channel_store.get(channel_id).messages  # includes the new user message
    ]
    ai_reply = get_chat_response(
        messages_for_llm,
        channel.customer_email,
        channel.subject,
    )
    channel_store.add_message(channel_id, "assistant", ai_reply)
    updated = channel_store.get(channel_id)
    return {
        "channel_id": channel_id,
        "user_message": body.content,
        "assistant_message": ai_reply,
        "messages": updated.messages if updated else [],
    }


# --- Superuser admin dashboard ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(email: str = Depends(require_superuser)):
    """Serve the superuser admin dashboard (tickets, channels, users CRUD)."""
    html_path = Path(__file__).parent / "templates" / "admin.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Admin template not found")


@app.get("/admin/api/tickets")
async def admin_list_tickets(_: str = Depends(require_superuser)):
    """List all tickets for admin."""
    tickets = store.list_all()
    return [
        {
            "id": t.id,
            "subject": t.subject,
            "description": t.description,
            "customer_email": t.customer_email,
            "status": t.status.value,
            "ai_response": t.ai_response or "",
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        for t in tickets
    ]


@app.post("/admin/api/tickets", response_model=TicketResponse)
async def admin_create_ticket(data: TicketCreate, _: str = Depends(require_superuser)):
    """Create a ticket (admin) and generate AI response."""
    try:
        ticket = store.create(data)
        ai_response = get_support_response(
            ticket.subject, ticket.description, ticket.customer_email
        )
        store.update_ai_response(ticket.id, ai_response)
        t = store.get(ticket.id)
        if not t:
            raise HTTPException(status_code=500, detail="Failed to retrieve created ticket")
        return TicketResponse(
            ticket_id=t.id,
            subject=t.subject,
            description=t.description,
            status=t.status,
            ai_response=t.ai_response or "",
            created_at=t.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e) if str(e) else "Failed to create ticket")


@app.get("/admin/api/tickets/{ticket_id}")
async def admin_get_ticket(ticket_id: str, _: str = Depends(require_superuser)):
    """Get one ticket for admin."""
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "description": ticket.description,
        "customer_email": ticket.customer_email,
        "status": ticket.status.value,
        "ai_response": ticket.ai_response or "",
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
    }


@app.patch("/admin/api/tickets/{ticket_id}")
async def admin_update_ticket(
    ticket_id: str,
    body: TicketUpdateRequest,
    _: str = Depends(require_superuser),
):
    """Update a ticket (admin)."""
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    payload = {}
    if body.subject is not None:
        payload["subject"] = body.subject
    if body.description is not None:
        payload["description"] = body.description
    if body.status is not None:
        payload["status"] = body.status
    if body.ai_response is not None:
        payload["ai_response"] = body.ai_response
    if not payload:
        return {
            "id": ticket.id,
            "subject": ticket.subject,
            "description": ticket.description,
            "customer_email": ticket.customer_email,
            "status": ticket.status.value,
            "ai_response": ticket.ai_response or "",
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
        }
    updated = store.update(
        ticket_id,
        subject=body.subject,
        description=body.description,
        status=body.status,
        ai_response=body.ai_response,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update ticket")
    return {
        "id": updated.id,
        "subject": updated.subject,
        "description": updated.description,
        "customer_email": updated.customer_email,
        "status": updated.status.value,
        "ai_response": updated.ai_response or "",
        "created_at": updated.created_at.isoformat(),
        "updated_at": updated.updated_at.isoformat(),
    }


@app.delete("/admin/api/tickets/{ticket_id}")
async def admin_delete_ticket(ticket_id: str, _: str = Depends(require_superuser)):
    """Delete a ticket (admin)."""
    if not store.delete(ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ok": True, "id": ticket_id}


@app.get("/admin/api/channels")
async def admin_list_channels(_: str = Depends(require_superuser)):
    """List all channels for admin."""
    channels = channel_store.list_all()
    return [
        {
            "id": c.id,
            "customer_email": c.customer_email,
            "subject": c.subject or "",
            "message_count": len(c.messages),
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in channels
    ]


@app.get("/admin/api/channels/{channel_id}")
async def admin_get_channel(channel_id: str, _: str = Depends(require_superuser)):
    """Get one channel with messages for admin."""
    channel = channel_store.get(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {
        "id": channel.id,
        "customer_email": channel.customer_email,
        "subject": channel.subject or "",
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in channel.messages
        ],
        "created_at": channel.created_at.isoformat(),
        "updated_at": channel.updated_at.isoformat(),
    }


@app.post("/admin/api/channels", response_model=ChannelResponse)
async def admin_create_channel(data: ChannelCreate, _: str = Depends(require_superuser)):
    """Create a channel (admin)."""
    channel = channel_store.create(data)
    if data.initial_message:
        messages_for_llm = [{"role": "user", "content": data.initial_message.strip()}]
        ai_reply = get_chat_response(
            messages_for_llm,
            channel.customer_email,
            channel.subject,
        )
        channel_store.add_message(channel.id, "assistant", ai_reply)
    ch = channel_store.get(channel.id)
    if not ch:
        raise HTTPException(status_code=500, detail="Failed to retrieve created channel")
    return ChannelResponse(
        channel_id=ch.id,
        customer_email=ch.customer_email,
        subject=ch.subject,
        messages=ch.messages,
        created_at=ch.created_at,
        updated_at=ch.updated_at,
    )


@app.delete("/admin/api/channels/{channel_id}")
async def admin_delete_channel(channel_id: str, _: str = Depends(require_superuser)):
    """Delete a channel (admin)."""
    if not channel_store.delete(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"ok": True, "id": channel_id}


@app.get("/admin/api/users")
async def admin_list_users(_: str = Depends(require_superuser)):
    """List all users for admin."""
    emails = user_list_all()
    return [{"email": e} for e in emails]


@app.delete("/admin/api/users/{email:path}")
async def admin_delete_user(email: str, _: str = Depends(require_superuser)):
    """Delete a user by email (admin)."""
    if not user_store_delete(email):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "email": email}
