"""Phase 2 — Hot and cold memory unit tests."""

import json

from app.memory.hot_memory import load_hot_to_redis, get_hot_from_redis
from app.memory.cold_memory import (
    load_cold_to_redis,
    get_cold_value,
    get_all_cold_ids,
    get_all_cold_memories,
    flush_cold,
)
from app.models.memory import Memory, MemoryType
from app.db.redis_client import session_hot_key, session_cold_key


class TestHotMemory:
    """Tests for hot memory Redis caching."""

    async def test_cache_hot_memory_writes_correct_redis_key(self, mock_redis):
        """Loading hot memories should write correct Redis keys."""
        await Memory(
            user_id="usr_1", type=MemoryType.HOT, field="name", content="Aryan"
        ).insert()
        await Memory(
            user_id="usr_1", type=MemoryType.HOT, field="age", content="22"
        ).insert()

        result = await load_hot_to_redis("sess_1", "usr_1")
        assert result == {"name": "Aryan", "age": "22"}

        val = await mock_redis.get(session_hot_key("sess_1", "name"))
        assert val == "Aryan"

    async def test_get_hot_memory_reads_from_redis_not_mongo(self, mock_redis):
        """Getting hot memory should read from Redis."""
        await mock_redis.set(session_hot_key("sess_1", "city"), "Mumbai")
        result = await get_hot_from_redis("sess_1")
        assert result["city"] == "Mumbai"

    async def test_missing_hot_key_returns_empty(self, mock_redis):
        """No hot memories returns empty dict."""
        result = await get_hot_from_redis("no_session")
        assert result == {}


class TestColdMemory:
    """Tests for cold memory Redis caching."""

    async def test_cache_cold_memory_writes_correct_key(self, mock_redis):
        """Loading cold memories should write correct Redis keys."""
        mem = await Memory(
            user_id="usr_1",
            type=MemoryType.COLD,
            content="Met girlfriend on Oct 3rd",
            subtype="relationship_event",
        ).insert()

        count = await load_cold_to_redis("sess_1", "usr_1")
        assert count == 1

        val = await mock_redis.get(session_cold_key("sess_1", str(mem.id)))
        assert val is not None
        data = json.loads(val)
        assert data["content"] == "Met girlfriend on Oct 3rd"

    async def test_get_all_cold_ids_returns_full_set(self, mock_redis):
        """All cold memory IDs should be in the Redis SET."""
        for i in range(3):
            await Memory(
                user_id="usr_1",
                type=MemoryType.COLD,
                content=f"Memory {i}",
            ).insert()

        await load_cold_to_redis("sess_1", "usr_1")
        ids = await get_all_cold_ids("sess_1")
        assert len(ids) == 3

    async def test_get_all_cold_memories_resolves_all_ids(self, mock_redis):
        """Resolving all IDs should return full memory entries."""
        for i in range(2):
            await Memory(
                user_id="usr_1",
                type=MemoryType.COLD,
                content=f"Memory {i}",
            ).insert()

        await load_cold_to_redis("sess_1", "usr_1")
        memories = await get_all_cold_memories("sess_1")
        assert len(memories) == 2
        contents = {m["content"] for m in memories}
        assert "Memory 0" in contents
        assert "Memory 1" in contents

    async def test_flush_session_removes_all_keys(self, mock_redis):
        """Flushing should remove all cold keys for the session."""
        await Memory(
            user_id="usr_1",
            type=MemoryType.COLD,
            content="To be flushed",
        ).insert()

        await load_cold_to_redis("sess_1", "usr_1")
        ids_before = await get_all_cold_ids("sess_1")
        assert len(ids_before) == 1

        await flush_cold("sess_1")

        ids_after = await get_all_cold_ids("sess_1")
        assert len(ids_after) == 0
