"""Cold memory module — Redis caching for cold (on-demand) memories."""

import json

from app.db.redis_client import get_redis, session_cold_key, session_cold_ids_key
from app.db.repositories import memory_repo


async def load_cold_to_redis(session_id: str, user_id: str) -> int:
    """Load all cold memories from MongoDB and cache in Redis.

    Returns:
        Number of cold memories cached.
    """
    memories = await memory_repo.get_cold_memories(user_id)
    if not memories:
        return 0

    r = get_redis()
    pipe = r.pipeline()
    mem_ids = []

    for mem in memories:
        mem_id = str(mem.id)
        mem_data = {
            "id": mem_id,
            "content": mem.content,
            "tag": mem.tag,
            "subtype": mem.subtype,
            "entities": mem.entities,
            "emotional_weight": mem.emotional_weight,
        }
        pipe.set(session_cold_key(session_id, mem_id), json.dumps(mem_data))
        mem_ids.append(mem_id)

    if mem_ids:
        pipe.sadd(session_cold_ids_key(session_id), *mem_ids)

    await pipe.execute()
    return len(mem_ids)


async def get_cold_value(session_id: str, mem_id: str) -> dict | None:
    """Retrieve a single cold memory from Redis by ID."""
    r = get_redis()
    raw = await r.get(session_cold_key(session_id, mem_id))
    if raw is None:
        return None
    return json.loads(raw)


async def get_all_cold_ids(session_id: str) -> set[str]:
    """Return the set of all cold memory IDs cached for this session."""
    r = get_redis()
    return await r.smembers(session_cold_ids_key(session_id))


async def get_all_cold_memories(session_id: str) -> list[dict]:
    """Resolve all cold memory IDs to their full values from Redis."""
    ids = await get_all_cold_ids(session_id)
    if not ids:
        return []

    r = get_redis()
    keys = [session_cold_key(session_id, mid) for mid in ids]
    values = await r.mget(keys)

    result = []
    for v in values:
        if v is not None:
            result.append(json.loads(v))
    return result


async def flush_cold(session_id: str) -> None:
    """Delete all cold memory keys for a session from Redis."""
    r = get_redis()
    ids = await get_all_cold_ids(session_id)

    if ids:
        pipe = r.pipeline()
        for mid in ids:
            pipe.delete(session_cold_key(session_id, mid))
        pipe.delete(session_cold_ids_key(session_id))
        await pipe.execute()
