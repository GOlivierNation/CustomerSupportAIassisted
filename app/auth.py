import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, HTTPException

from app.db import get_supabase, use_supabase

SESSION_COOKIE_NAME = "customer_session"

# In-memory session store when Supabase is not used
_sessions: dict[str, str] = {}

# Session duration in seconds (7 days)
SESSION_MAX_AGE = 86400 * 7


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def create_session(customer_email: str) -> str:
    """Create a session for the customer, return session_id."""
    session_id = secrets.token_urlsafe(32)
    email = customer_email.strip().lower()
    if use_supabase():
        sb = get_supabase()
        from datetime import timedelta
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=SESSION_MAX_AGE)).isoformat()
        sb.table("sessions").insert({
            "session_id": session_id,
            "customer_email": email,
            "expires_at": expires_at,
        }).execute()
    else:
        _sessions[session_id] = email
    return session_id


def get_email_for_session(session_id: Optional[str]) -> Optional[str]:
    if not session_id:
        return None
    if use_supabase():
        try:
            sb = get_supabase()
            res = sb.table("sessions").select("customer_email, expires_at").eq("session_id", session_id).execute()
            if not res.data or len(res.data) == 0:
                return None
            row = res.data[0]
            expires_at = _parse_iso(row.get("expires_at"))
            if expires_at and expires_at < datetime.now(timezone.utc):
                sb.table("sessions").delete().eq("session_id", session_id).execute()
                return None
            return row.get("customer_email")
        except Exception:
            return None
    return _sessions.get(session_id)


def destroy_session(session_id: Optional[str]) -> None:
    if not session_id:
        return
    if use_supabase():
        sb = get_supabase()
        sb.table("sessions").delete().eq("session_id", session_id).execute()
    elif session_id in _sessions:
        del _sessions[session_id]


async def get_current_customer_email(
    customer_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Optional[str]:
    """Return the logged-in customer email if session is valid, else None."""
    return get_email_for_session(customer_session)


async def require_customer(
    customer_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> str:
    """Dependency: require a valid session; raise 401 if not logged in."""
    email = get_email_for_session(customer_session)
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Please log in to access this page",
            headers={"Location": "/login"},
        )
    return email
