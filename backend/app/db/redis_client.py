"""Redis client and session namespace key builders."""

import redis.asyncio as redis

from app.config import settings

pool: redis.Redis | None = None


async def init_redis():
    """Initialize the async Redis connection pool."""
    global pool
    pool = redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis():
    """Close the Redis connection pool."""
    global pool
    if pool:
        await pool.aclose()
        pool = None


def get_redis() -> redis.Redis:
    """Return the active Redis client. Raises if not initialized."""
    if pool is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return pool


# ─── Session namespace key builders ──────────────────────────────────────────


def session_hot_key(session_id: str, field: str) -> str:
    """Key for a single hot memory field within a session."""
    return f"session:{session_id}:hot:{field}"


def session_cold_key(session_id: str, mem_id: str) -> str:
    """Key for a single cold memory entry within a session."""
    return f"session:{session_id}:cold:{mem_id}"


def session_cold_ids_key(session_id: str) -> str:
    """Key for the SET of all cold memory IDs within a session."""
    return f"session:{session_id}:cold_ids"


def session_prompt_key(session_id: str) -> str:
    """Key for the assembled system prompt within a session."""
    return f"session:{session_id}:prompt"


def session_history_key(session_id: str) -> str:
    """Key for the LIST of recent conversation turns within a session."""
    return f"session:{session_id}:history"


def session_status_key(session_id: str) -> str:
    """Key for session status (active / ended)."""
    return f"session:{session_id}:status"
