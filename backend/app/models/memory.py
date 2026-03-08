"""Memory document model — supports both hot and cold memory types."""

from datetime import datetime
from enum import Enum

from beanie import Document
from pydantic import Field


class MemoryType(str, Enum):
    """Discriminator for hot vs cold memory."""

    HOT = "hot"
    COLD = "cold"


class Memory(Document):
    """A single memory entry belonging to a user.

    Hot memories: core user facts (name, age, city) — always in system prompt.
    Cold memories: episodic memories — retrieved on demand via Gemini SDK.
    """

    user_id: str
    type: MemoryType
    tag: str | None = None  # personal / professional / health (Phase 2)
    subtype: str | None = None  # relationship_event, daily_context, etc.
    field: str | None = None  # only for hot memories (e.g. "name", "age")
    content: str
    entities: list[str] = Field(default_factory=list)
    emotional_weight: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime | None = None
    access_count: int = 0
    expires_at: datetime | None = None

    class Settings:
        name = "memories"
