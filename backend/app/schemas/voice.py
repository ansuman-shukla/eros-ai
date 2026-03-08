"""Voice API request and response schemas."""

from pydantic import BaseModel


# ─── Token endpoint ──────────────────────────────────────────────────────────


class VoiceTokenResponse(BaseModel):
    """Response from POST /api/v1/voice/token."""

    session_id: str
    livekit_token: str
    room_name: str


# ─── Internal voice-turn endpoint ────────────────────────────────────────────


class VoiceTurnRequest(BaseModel):
    """Request body for POST /internal/voice-turn."""

    session_id: str
    transcript_text: str


class VoiceTurnResponse(BaseModel):
    """Response from POST /internal/voice-turn."""

    response_text: str
    filler_text: str | None = None
    memory_used: bool = False


# ─── Internal voice-interrupt endpoint ───────────────────────────────────────


class VoiceInterruptRequest(BaseModel):
    """Request body for POST /internal/voice-interrupt."""

    session_id: str
    turn_id: int
