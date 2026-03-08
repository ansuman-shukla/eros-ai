"""Hot memory module — Redis caching for hot (always-in-prompt) memories."""

import json

from app.db.redis_client import get_redis, session_hot_key
from app.db.repositories import memory_repo


async def load_hot_to_redis(session_id: str, user_id: str) -> dict[str, str]:
    """Load all hot memories from MongoDB and cache in Redis.

    Returns:
        Dict of field → value pairs cached.
    """
    memories = await memory_repo.get_hot_memories(user_id)
    if not memories:
        return {}

    r = get_redis()
    pipe = r.pipeline()
    result = {}

    for mem in memories:
        if mem.field:
            key = session_hot_key(session_id, mem.field)
            pipe.set(key, mem.content)
            result[mem.field] = mem.content

    await pipe.execute()
    return result


async def get_hot_from_redis(session_id: str) -> dict[str, str]:
    """Retrieve all hot memory fields from Redis for the session.

    Uses a scan-based approach to find all hot keys for the session.
    """
    r = get_redis()
    pattern = f"session:{session_id}:hot:*"
    result = {}

    async for key in r.scan_iter(match=pattern):
        field = key.split(":")[-1]
        value = await r.get(key)
        if value is not None:
            result[field] = value

    return result
