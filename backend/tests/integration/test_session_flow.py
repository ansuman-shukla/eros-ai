"""Phase 2 — Session and memory integration tests."""

import pytest
from httpx import AsyncClient

from app.models.memory import Memory, MemoryType
from app.models.session import Session
from app.db.redis_client import get_redis, session_hot_key, session_cold_ids_key, session_status_key


class TestMemoryCRUD:
    """Integration tests for memory CRUD endpoints."""

    async def test_create_hot_memory_persists_to_mongo(self, client: AsyncClient, seeded_user):
        resp = await client.post(
            "/api/v1/memory/",
            json={"type": "hot", "field": "name", "content": "Aryan"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "hot"
        assert data["content"] == "Aryan"

        mem = await Memory.get(data["id"])
        assert mem is not None

    async def test_create_cold_memory_persists_with_correct_subtype(self, client: AsyncClient, seeded_user):
        resp = await client.post(
            "/api/v1/memory/",
            json={
                "type": "cold",
                "content": "Got a new job",
                "subtype": "career_event",
                "tag": "professional",
            },
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subtype"] == "career_event"
        assert data["tag"] == "professional"

    async def test_update_memory_modifies_existing_doc(self, client: AsyncClient, seeded_user):
        create = await client.post(
            "/api/v1/memory/",
            json={"type": "cold", "content": "Original content"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        mem_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/memory/{mem_id}",
            json={"content": "Updated content"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated content"

    async def test_delete_memory_removes_from_mongo(self, client: AsyncClient, seeded_user):
        create = await client.post(
            "/api/v1/memory/",
            json={"type": "cold", "content": "Delete me"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        mem_id = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/memory/{mem_id}",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 204

        mem = await Memory.get(mem_id)
        assert mem is None


class TestSessionLifecycle:
    """Integration tests for session init and end."""

    async def test_session_init_creates_mongo_doc(self, client: AsyncClient, seeded_user):
        resp = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 201
        session_id = resp.json()["session_id"]

        session = await Session.get(session_id)
        assert session is not None
        assert session.status == "active"
        assert session.mode == "chat"

    async def test_session_init_loads_hot_memory_into_redis(self, client: AsyncClient, seeded_user):
        # Create a hot memory first
        await client.post(
            "/api/v1/memory/",
            json={"type": "hot", "field": "name", "content": "TestUser"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        resp = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        session_id = resp.json()["session_id"]

        r = get_redis()
        val = await r.get(session_hot_key(session_id, "name"))
        assert val == "TestUser"

    async def test_session_init_loads_cold_memory_into_redis(self, client: AsyncClient, seeded_user):
        await client.post(
            "/api/v1/memory/",
            json={"type": "cold", "content": "Cold memory test"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        resp = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        session_id = resp.json()["session_id"]

        r = get_redis()
        ids = await r.smembers(session_cold_ids_key(session_id))
        assert len(ids) == 1

    async def test_session_end_marks_mongo_doc_ended(self, client: AsyncClient, seeded_user):
        init = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        session_id = init.json()["session_id"]

        resp = await client.post(
            f"/api/v1/session/{session_id}/end",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ended"

        session = await Session.get(session_id)
        assert session.status == "ended"
        assert session.ended_at is not None

    async def test_session_end_clears_all_redis_keys(self, client: AsyncClient, seeded_user):
        await client.post(
            "/api/v1/memory/",
            json={"type": "hot", "field": "city", "content": "Mumbai"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        init = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        session_id = init.json()["session_id"]

        # Verify key exists before end
        r = get_redis()
        assert await r.get(session_status_key(session_id)) == "active"

        await client.post(
            f"/api/v1/session/{session_id}/end",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        # All session keys should be gone
        assert await r.get(session_status_key(session_id)) is None
        assert await r.get(session_hot_key(session_id, "city")) is None

    async def test_no_db_read_during_active_session_memory_access(self, client: AsyncClient, seeded_user):
        """Memory reads during an active session should only hit Redis."""
        await client.post(
            "/api/v1/memory/",
            json={"type": "hot", "field": "lang", "content": "en"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        init = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        session_id = init.json()["session_id"]

        # Read from Redis directly (no DB call)
        from app.memory.hot_memory import get_hot_from_redis
        result = await get_hot_from_redis(session_id)
        assert result["lang"] == "en"
