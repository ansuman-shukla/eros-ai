"""LiveKit token service — generates room access tokens for voice sessions."""

from datetime import timedelta

from livekit.api import AccessToken, VideoGrants

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_room_token(user_id: str, session_id: str) -> str:
    """Generate a LiveKit room token for a voice session.

    Room name convention: companion-{session_id}

    Args:
        user_id: The user's document ID (used as participant identity).
        session_id: The session document ID (used in room name).

    Returns:
        A signed JWT string for the LiveKit room.
    """
    room_name = f"companion-{session_id}"

    token = (
        AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(user_id)
        .with_name(f"user-{user_id}")
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        .with_ttl(timedelta(hours=1))
        .to_jwt()
    )

    logger.info(f"LiveKit token generated: user={user_id}, room={room_name}")
    return token


def get_room_name(session_id: str) -> str:
    """Get the room name for a session.

    Args:
        session_id: The session document ID.

    Returns:
        The LiveKit room name.
    """
    return f"companion-{session_id}"
