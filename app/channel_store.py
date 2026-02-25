import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.db import get_supabase, use_supabase
from app.models import Channel, ChannelCreate, ChannelMessage


def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


class ChannelStore:
    """Channel store. Uses Supabase when configured, else in-memory."""

    def __init__(self) -> None:
        self._channels: Dict[str, Channel] = {}

    def create(self, data: ChannelCreate) -> Channel:
        channel_id = str(uuid.uuid4())[:8]
        messages: list[ChannelMessage] = []
        if data.initial_message:
            messages.append(
                ChannelMessage(role="user", content=data.initial_message.strip())
            )
        channel = Channel(
            id=channel_id,
            customer_email=data.customer_email,
            subject=data.subject,
            messages=messages,
        )
        if use_supabase():
            sb = get_supabase()
            now = datetime.now(timezone.utc).isoformat()
            email_lower = data.customer_email.strip().lower()
            sb.table("channels").insert({
                "id": channel_id,
                "customer_email": email_lower,
                "subject": data.subject,
                "created_at": now,
                "updated_at": now,
            }).execute()
            if data.initial_message:
                sb.table("channel_messages").insert({
                    "channel_id": channel_id,
                    "role": "user",
                    "content": data.initial_message.strip(),
                }).execute()
        else:
            self._channels[channel_id] = channel
        return channel

    def get(self, channel_id: str) -> Optional[Channel]:
        if use_supabase():
            sb = get_supabase()
            ch_res = sb.table("channels").select("*").eq("id", channel_id).execute()
            if not ch_res.data or len(ch_res.data) == 0:
                return None
            row = ch_res.data[0]
            msg_res = sb.table("channel_messages").select("*").eq("channel_id", channel_id).order("created_at").execute()
            messages = [
                ChannelMessage(
                    role=m["role"],
                    content=m["content"],
                    created_at=_parse_dt(m.get("created_at")),
                )
                for m in (msg_res.data or [])
            ]
            return Channel(
                id=row["id"],
                customer_email=row["customer_email"],
                subject=row.get("subject"),
                messages=messages,
                created_at=_parse_dt(row.get("created_at")),
                updated_at=_parse_dt(row.get("updated_at")),
            )
        return self._channels.get(channel_id)

    def add_message(self, channel_id: str, role: str, content: str) -> Optional[Channel]:
        if use_supabase():
            sb = get_supabase()
            sb.table("channel_messages").insert({
                "channel_id": channel_id,
                "role": role,
                "content": content,
            }).execute()
            now = datetime.now(timezone.utc).isoformat()
            sb.table("channels").update({"updated_at": now}).eq("id", channel_id).execute()
            return self.get(channel_id)
        channel = self._channels.get(channel_id)
        if not channel:
            return None
        channel.messages.append(ChannelMessage(role=role, content=content))
        channel.updated_at = datetime.now(timezone.utc)
        return channel

    def list_all(self) -> list[Channel]:
        if use_supabase():
            sb = get_supabase()
            res = sb.table("channels").select("id").order("updated_at", desc=True).execute()
            channels = []
            for row in (res.data or []):
                ch = self.get(row["id"])
                if ch:
                    channels.append(ch)
            return channels
        return sorted(
            self._channels.values(),
            key=lambda c: c.updated_at,
            reverse=True,
        )


channel_store = ChannelStore()
