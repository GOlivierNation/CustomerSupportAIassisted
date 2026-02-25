import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.db import get_supabase, use_supabase
from app.models import Ticket, TicketCreate, TicketStatus


def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _row_to_ticket(row: dict) -> Ticket:
    return Ticket(
        id=row["id"],
        subject=row["subject"],
        description=row["description"],
        customer_email=row["customer_email"],
        status=TicketStatus(row["status"]),
        ai_response=row.get("ai_response"),
        created_at=_parse_dt(row.get("created_at")),
        updated_at=_parse_dt(row.get("updated_at")),
    )


class TicketStore:
    """Ticket store. Uses Supabase when configured, else in-memory."""

    def __init__(self) -> None:
        self._tickets: Dict[str, Ticket] = {}

    def create(self, data: TicketCreate) -> Ticket:
        ticket_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        ticket = Ticket(
            id=ticket_id,
            subject=data.subject,
            description=data.description,
            customer_email=data.customer_email,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        if use_supabase():
            sb = get_supabase()
            email_lower = data.customer_email.strip().lower()
            sb.table("tickets").insert({
                "id": ticket_id,
                "subject": data.subject,
                "description": data.description,
                "customer_email": email_lower,
                "status": TicketStatus.OPEN.value,
                "ai_response": None,
                "created_at": now,
                "updated_at": now,
            }).execute()
        else:
            self._tickets[ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> Optional[Ticket]:
        if use_supabase():
            sb = get_supabase()
            res = sb.table("tickets").select("*").eq("id", ticket_id).execute()
            if not res.data or len(res.data) == 0:
                return None
            return _row_to_ticket(res.data[0])
        return self._tickets.get(ticket_id)

    def update_ai_response(self, ticket_id: str, ai_response: str) -> Optional[Ticket]:
        if use_supabase():
            sb = get_supabase()
            now = datetime.now(timezone.utc).isoformat()
            sb.table("tickets").update({
                "ai_response": ai_response,
                "status": TicketStatus.IN_PROGRESS.value,
                "updated_at": now,
            }).eq("id", ticket_id).execute()
            return self.get(ticket_id)
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        ticket.ai_response = ai_response
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.updated_at = datetime.now(timezone.utc)
        return ticket

    def list_all(self) -> list[Ticket]:
        if use_supabase():
            sb = get_supabase()
            res = sb.table("tickets").select("*").order("created_at", desc=True).execute()
            return [_row_to_ticket(row) for row in (res.data or [])]
        return sorted(self._tickets.values(), key=lambda t: t.created_at, reverse=True)

    def list_by_email(self, customer_email: str) -> list[Ticket]:
        email_lower = customer_email.strip().lower()
        if use_supabase():
            sb = get_supabase()
            res = sb.table("tickets").select("*").eq("customer_email", email_lower).order("created_at", desc=True).execute()
            return [_row_to_ticket(row) for row in (res.data or [])]
        return sorted(
            [t for t in self._tickets.values() if t.customer_email.lower() == email_lower],
            key=lambda t: t.created_at,
            reverse=True,
        )

    def update_status(self, ticket_id: str, status: TicketStatus) -> Optional[Ticket]:
        if use_supabase():
            sb = get_supabase()
            now = datetime.now(timezone.utc).isoformat()
            sb.table("tickets").update({"status": status.value, "updated_at": now}).eq("id", ticket_id).execute()
            return self.get(ticket_id)
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        ticket.status = status
        ticket.updated_at = datetime.now(timezone.utc)
        return ticket


store = TicketStore()
