"""Session document model with embedded Turn sub-documents."""

from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field


class Turn(BaseModel):
    """A single conversation turn (user or agent) within a session."""

    turn_id: int
    mode: str = "chat"  # "chat" | "voice"
    role: str  # "user" | "agent"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    memory_used: bool = False
    filler_used: bool = False
    interrupted: bool = False


class Session(Document):
    """Represents a single conversation session (chat or voice)."""

    user_id: str
    mode: str = "chat"  # "chat" | "voice"
    status: str = "active"  # "active" | "ended"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    turns: list[Turn] = Field(default_factory=list)

    class Settings:
        name = "sessions"
