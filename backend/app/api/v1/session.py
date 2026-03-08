"""Session API routes — init and end session lifecycle."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.session import SessionInitRequest, SessionInitResponse, SessionEndResponse
from app.core.session_manager import init_session, end_session

router = APIRouter()


@router.post("/init", response_model=SessionInitResponse, status_code=201)
async def session_init(body: SessionInitRequest, user: User = Depends(get_current_user)):
    """Initialize a new chat or voice session.

    Loads all user memories into Redis for the session duration.
    """
    session_id = await init_session(str(user.id), body.mode)
    return SessionInitResponse(session_id=session_id)


@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def session_end(session_id: str, user: User = Depends(get_current_user)):
    """End an active session.

    Flushes Redis, persists state to MongoDB, and enqueues background jobs.
    """
    await end_session(session_id)
    return SessionEndResponse(status="ended")
