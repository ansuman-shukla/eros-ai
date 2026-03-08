"""WebSocket chat route — real-time chat over WebSocket."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.utils.jwt import decode_token
from app.models.user import User
from app.models.session import Session
from app.core.response_streamer import stream_chat_response
from app.core.prompt_builder import assemble_prompt
from app.utils.logger import get_logger

from jose import JWTError

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/session/{session_id}/chat")
async def chat_ws(websocket: WebSocket, session_id: str, token: str = Query(default="")):
    """WebSocket endpoint for real-time chat.

    Authenticate via query param `?token=<jwt>`.
    Each message from the client triggers a streamed response.

    Args:
        websocket: The WebSocket connection.
        session_id: Active session ID.
        token: JWT access token (query parameter).
    """
    # Authenticate
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        user_id = decode_token(token)
        user = await User.get(user_id)
        if user is None:
            await websocket.close(code=4001, reason="User not found")
            return
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify session exists and is active
    session = await Session.get(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    if session.status != "active":
        await websocket.close(code=4004, reason="Session not active")
        return

    # Accept the connection
    await websocket.accept()

    # Assemble prompt on first connection
    await assemble_prompt(session_id, str(user.id))

    logger.info(f"WebSocket connected: user={user_id}, session={session_id}")

    try:
        while True:
            # Receive user message
            data = await websocket.receive_text()

            if not data.strip():
                continue

            # Stream response
            await stream_chat_response(
                session_id=session_id,
                query=data.strip(),
                websocket=websocket,
                user_id=str(user.id),
            )

            # Send end-of-response marker
            await websocket.send_text("[EOR]")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={user_id}, session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=4500, reason="Internal error")
        except Exception:
            pass
