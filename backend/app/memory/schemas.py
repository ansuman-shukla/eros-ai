"""Pydantic models for memory retrieval pipeline."""

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    """A cold memory entry as stored in Redis."""

    id: str
    content: str
    tag: str | None = None
    subtype: str | None = None
    entities: list[str] = []
    emotional_weight: float = 0.0
