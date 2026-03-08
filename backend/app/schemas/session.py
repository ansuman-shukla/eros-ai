"""Session request/response schemas."""

from pydantic import BaseModel


class SessionInitRequest(BaseModel):
    mode: str = "chat"  # "chat" | "voice"


class SessionInitResponse(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    status: str = "ended"
