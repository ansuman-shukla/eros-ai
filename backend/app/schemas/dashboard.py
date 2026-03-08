"""Dashboard and persona API response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# ─── Personality ─────────────────────────────────────────────────────────────


class PersonalityResponse(BaseModel):
    """Full personality profile for the dashboard."""

    user_id: str
    jungian_type: str | None = None
    type_confidence: float = 0.0
    archetypes: list[dict] = Field(default_factory=list)
    trait_weights: dict[str, float] = Field(default_factory=dict)
    attachment_style: str | None = None
    cognitive_style: str | None = None
    core_values: list[str] = Field(default_factory=list)
    version: int = 0
    last_updated: datetime | None = None


# ─── Activity ────────────────────────────────────────────────────────────────


class DayActivity(BaseModel):
    """Activity counts for a single day."""

    date: str  # ISO date, e.g. "2024-11-21"
    session_count: int = 0
    turn_count: int = 0
    chat_turns: int = 0
    voice_turns: int = 0


class ActivityResponse(BaseModel):
    """Per-day activity for the last 30 days."""

    user_id: str
    days: list[DayActivity] = Field(default_factory=list)
    total_sessions: int = 0
    total_turns: int = 0


# ─── Diary ───────────────────────────────────────────────────────────────────


class DiaryEntryResponse(BaseModel):
    """A single diary entry visible to the user."""

    id: str
    date: str
    content: str
    page_number: int
    created_at: datetime


class DiaryListResponse(BaseModel):
    """Paginated diary entries."""

    entries: list[DiaryEntryResponse] = Field(default_factory=list)
    total: int = 0
    pages_owned: int = 0
    page: int = 1
    page_size: int = 10


# ─── Traits ──────────────────────────────────────────────────────────────────


class TraitResponse(BaseModel):
    """A single trait from the trait library."""

    id: str
    name: str
    category: str
    prompt_modifier: str
    coin_cost: int = 0
    locked: bool = False
    is_active: bool = False


class TraitLibraryResponse(BaseModel):
    """Full trait library with active flags."""

    traits: list[TraitResponse] = Field(default_factory=list)
    active_trait_ids: list[str] = Field(default_factory=list)


# ─── Persona Update ─────────────────────────────────────────────────────────


class UpdateActiveTraitsRequest(BaseModel):
    """Request body for PATCH /api/v1/persona/active."""

    active_trait_ids: list[str]


class UpdateActiveTraitsResponse(BaseModel):
    """Response from updating active traits."""

    active_trait_ids: list[str]
    message: str = "Active traits updated."
