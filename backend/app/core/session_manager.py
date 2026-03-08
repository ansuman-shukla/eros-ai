"""Session manager — handles init and end lifecycle for chat/voice sessions."""

from datetime import datetime

from app.models.session import Session
from app.memory.hot_memory import load_hot_to_redis
from app.memory.cold_memory import load_cold_to_redis, flush_cold
from app.db.redis_client import get_redis, session_status_key, session_hot_key
from app.utils.errors import NotFoundError, SessionNotActiveError
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def init_session(user_id: str, mode: str = "chat") -> str:
    """Initialize a new session.

    1. Create Session document in MongoDB
    2. Load hot + cold memories into Redis
    3. Set session status to active in Redis
    4. Return session_id

    Args:
        user_id: The user's document ID.
        mode: "chat" or "voice".

    Returns:
        The new session's document ID as a string.
    """
    session = Session(user_id=user_id, mode=mode)
    await session.insert()
    session_id = str(session.id)

    # Load all memories into Redis
    hot_count = await load_hot_to_redis(session_id, user_id)
    cold_count = await load_cold_to_redis(session_id, user_id)

    # Mark session as active in Redis
    r = get_redis()
    await r.set(session_status_key(session_id), "active")

    logger.info(
        f"Session {session_id} initialized: mode={mode}, "
        f"hot={len(hot_count) if isinstance(hot_count, dict) else hot_count}, "
        f"cold={cold_count}"
    )
    return session_id


async def end_session(session_id: str) -> None:
    """End a session and trigger cleanup.

    1. Mark session ended in MongoDB
    2. Flush Redis session namespace
    3. Enqueue background worker jobs

    Args:
        session_id: The session document ID.

    Raises:
        NotFoundError: If the session doesn't exist.
        SessionNotActiveError: If the session is already ended.
    """
    session = await Session.get(session_id)
    if session is None:
        raise NotFoundError("Session", session_id)

    if session.status != "active":
        raise SessionNotActiveError(session_id)

    # Mark ended in MongoDB
    session.status = "ended"
    session.ended_at = datetime.utcnow()
    await session.save()

    # Flush Redis
    await flush_session_redis(session_id)

    # Enqueue background jobs
    try:
        from app.workers.queue import get_arq_pool
        pool = await get_arq_pool()
        await pool.enqueue_job("memory_curation_job", session_id)
        await pool.enqueue_job("personality_update_job", session_id)
        logger.info(f"Background jobs enqueued for session {session_id}")
    except Exception as e:
        logger.warning(f"Failed to enqueue background jobs: {e}")


async def flush_session_redis(session_id: str) -> None:
    """Clear all Redis keys for a session."""
    r = get_redis()

    # Flush cold memories
    await flush_cold(session_id)

    # Flush hot memories (scan and delete)
    hot_pattern = f"session:{session_id}:hot:*"
    async for key in r.scan_iter(match=hot_pattern):
        await r.delete(key)

    # Flush other session keys
    await r.delete(session_status_key(session_id))
    await r.delete(f"session:{session_id}:prompt")
    await r.delete(f"session:{session_id}:history")
