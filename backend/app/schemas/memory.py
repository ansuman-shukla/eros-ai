"""Memory request/response schemas."""

from pydantic import BaseModel


class MemoryCreateRequest(BaseModel):
    type: str  # "hot" | "cold"
    field: str | None = None  # for hot memories
    content: str
    tag: str | None = None
    subtype: str | None = None
    entities: list[str] = []
    emotional_weight: float = 0.0


class MemoryUpdateRequest(BaseModel):
    content: str | None = None
    tag: str | None = None
    subtype: str | None = None
    entities: list[str] | None = None
    emotional_weight: float | None = None


class MemoryResponse(BaseModel):
    id: str
    user_id: str
    type: str
    field: str | None = None
    content: str
    tag: str | None = None
    subtype: str | None = None
    entities: list[str] = []
    emotional_weight: float = 0.0
