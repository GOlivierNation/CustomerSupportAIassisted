from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    customer_email: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    customer_email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    customer_email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)


class UpdateTicketStatusRequest(BaseModel):
    status: TicketStatus


class Ticket(BaseModel):
    id: str
    subject: str
    description: str
    customer_email: str
    status: TicketStatus = TicketStatus.OPEN
    ai_response: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TicketResponse(BaseModel):
    ticket_id: str
    subject: str
    description: str
    status: TicketStatus
    ai_response: str
    created_at: datetime


# --- Channel (customer chat) models ---

class ChannelMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Channel(BaseModel):
    id: str
    customer_email: str
    subject: Optional[str] = None  # optional topic for context
    messages: list[ChannelMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChannelCreate(BaseModel):
    customer_email: str = Field(..., min_length=1)
    subject: Optional[str] = None
    initial_message: Optional[str] = None  # optional first message


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class ChannelResponse(BaseModel):
    channel_id: str
    customer_email: str
    subject: Optional[str] = None
    messages: list[ChannelMessage]
    created_at: datetime
    updated_at: datetime
