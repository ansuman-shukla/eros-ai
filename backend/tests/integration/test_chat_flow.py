"""Phase 3 — Chat pipeline integration tests (WebSocket + streamer)."""

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from httpx import AsyncClient

from app.models.memory import Memory, MemoryType
from app.models.session import Session
from app.models.coins import CoinLedger
from app.db.redis_client import get_redis, session_status_key


class TestChatIntegration:
    """Integration tests for the chat pipeline via WebSocket."""

    async def _setup_session(self, client: AsyncClient, seeded_user: dict):
        """Helper: create memories and init a session."""
        token = seeded_user["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a hot memory
        await client.post(
            "/api/v1/memory/",
            json={"type": "hot", "field": "name", "content": "Aryan"},
            headers=headers,
        )

        # Init session
        resp = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers=headers,
        )
        return resp.json()["session_id"]

    def _mock_gemini_stream(self, *chunks):
        """Create a mock that replaces _stream_llm."""
        async def fake_stream(system_prompt, messages):
            for chunk in chunks:
                yield chunk
        return fake_stream

    async def test_turn_appended_to_session_turns_in_mongo(self, client: AsyncClient, seeded_user):
        """After a chat turn, both user + agent turns should be in the Session."""
        session_id = await self._setup_session(client, seeded_user)

        with patch("app.core.response_streamer._stream_llm", self._mock_gemini_stream("NO_SEARCH", "\nHello Aryan!")):
            async with client.stream("GET", f"/ws/session/{session_id}/chat?token={seeded_user['token']}") as resp:
                pass  # WebSocket through httpx not supported, use direct test below

        # Test directly via response_streamer
        from app.core.response_streamer import stream_chat_response

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        with patch("app.core.response_streamer._stream_llm", self._mock_gemini_stream("NO_SEARCH", "\nHello Aryan!")):
            await stream_chat_response(session_id, "Hi there!", mock_ws, seeded_user["user_id"])

        session = await Session.get(session_id)
        assert len(session.turns) == 2
        assert session.turns[0].role == "user"
        assert session.turns[0].content == "Hi there!"
        assert session.turns[1].role == "agent"
        assert "Hello Aryan" in session.turns[1].content

    async def test_no_search_turn_streams_response(self, client: AsyncClient, seeded_user):
        """NO_SEARCH path should stream response chunks to WebSocket."""
        session_id = await self._setup_session(client, seeded_user)

        mock_ws = AsyncMock()
        sent_chunks = []
        mock_ws.send_text = AsyncMock(side_effect=lambda x: sent_chunks.append(x))

        with patch("app.core.response_streamer._stream_llm", self._mock_gemini_stream("NO_SEARCH", "\nHi ", "Aryan!")):
            from app.core.response_streamer import stream_chat_response
            await stream_chat_response(session_id, "Hello!", mock_ws, seeded_user["user_id"])

        # Should have received streamed chunks
        assert len(sent_chunks) >= 1
        full = "".join(sent_chunks)
        assert "Aryan" in full

    async def test_search_turn_retrieves_memory_and_enriches(self, client: AsyncClient, seeded_user):
        """SEARCH path should retrieve memories and use them."""
        session_id = await self._setup_session(client, seeded_user)
        token = seeded_user["token"]

        # Add cold memory
        await client.post(
            "/api/v1/memory/",
            json={"type": "cold", "content": "User's girlfriend name is Priya"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Re-init session to load cold memory
        resp = await client.post(
            "/api/v1/session/init",
            json={"mode": "chat"},
            headers={"Authorization": f"Bearer {token}"},
        )
        session_id = resp.json()["session_id"]

        call_count = [0]

        def make_stream(*chunks):
            async def stream(system_prompt, messages):
                call_count[0] += 1
                for chunk in chunks:
                    yield chunk
            return stream

        # First stream returns SEARCH, second returns enriched response
        streams = [
            make_stream("SEARCH"),
            make_stream("Your girlfriend ", "Priya is ", "wonderful!"),
        ]
        stream_idx = [0]

        async def multi_stream(system_prompt, messages):
            idx = stream_idx[0]
            stream_idx[0] += 1
            async for chunk in streams[min(idx, len(streams) - 1)](system_prompt, messages):
                yield chunk

        mock_ws = AsyncMock()
        sent = []
        mock_ws.send_text = AsyncMock(side_effect=lambda x: sent.append(x))

        # Mock Gemini retrieval to return the cold memory ID
        cold_mems = await Memory.find(
            Memory.user_id == seeded_user["user_id"],
            Memory.type == MemoryType.COLD,
        ).to_list()

        mock_retrieval_response = MagicMock()
        mock_retrieval_response.text = json.dumps([str(m.id) for m in cold_mems])

        with patch("app.core.response_streamer._stream_llm", multi_stream), \
             patch("app.memory.retrieval.get_gemini_client") as mock_gc:
            mock_gc.return_value.models.generate_content.return_value = mock_retrieval_response
            from app.core.response_streamer import stream_chat_response
            await stream_chat_response(session_id, "What's my girlfriend's name?", mock_ws, seeded_user["user_id"])

        session = await Session.get(session_id)
        agent_turn = session.turns[-1]
        assert agent_turn.memory_used is True

    async def test_coins_awarded_after_normal_message(self, client: AsyncClient, seeded_user):
        """Coins should be awarded after a chat message."""
        session_id = await self._setup_session(client, seeded_user)

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        with patch("app.core.response_streamer._stream_llm", self._mock_gemini_stream("NO_SEARCH", "\nHey!")):
            from app.core.response_streamer import stream_chat_response
            await stream_chat_response(session_id, "Hi", mock_ws, seeded_user["user_id"])

        ledger = await CoinLedger.find_one(CoinLedger.user_id == seeded_user["user_id"])
        assert ledger.total_coins == 10
        assert ledger.daily_earned_today == 10

    async def test_daily_coin_cap_not_exceeded(self, client: AsyncClient, seeded_user):
        """Coins should not exceed daily cap."""
        session_id = await self._setup_session(client, seeded_user)

        # Pre-set ledger to near cap
        ledger = await CoinLedger.find_one(CoinLedger.user_id == seeded_user["user_id"])
        ledger.daily_earned_today = 95
        from datetime import date
        ledger.last_reset_date = date.today().isoformat()
        await ledger.save()

        mock_ws = AsyncMock()
        mock_ws.send_text = AsyncMock()

        with patch("app.core.response_streamer._stream_llm", self._mock_gemini_stream("NO_SEARCH", "\nHey!")):
            from app.core.response_streamer import stream_chat_response
            await stream_chat_response(session_id, "Hi", mock_ws, seeded_user["user_id"])

        ledger = await CoinLedger.find_one(CoinLedger.user_id == seeded_user["user_id"])
        assert ledger.daily_earned_today <= 100  # capped

    async def test_no_cold_memory_session_responds_gracefully(self, client: AsyncClient, seeded_user):
        """A session with no cold memories (SEARCH) should still respond."""
        session_id = await self._setup_session(client, seeded_user)

        mock_ws = AsyncMock()
        sent = []
        mock_ws.send_text = AsyncMock(side_effect=lambda x: sent.append(x))

        # SEARCH decision, but no cold memories → retrieval returns empty
        streams = [
            self._mock_gemini_stream("SEARCH"),
            self._mock_gemini_stream("Sorry, I don't recall."),
        ]
        stream_idx = [0]

        async def multi_stream(system_prompt, messages):
            idx = stream_idx[0]
            stream_idx[0] += 1
            async for chunk in streams[min(idx, len(streams)-1)](system_prompt, messages):
                yield chunk

        with patch("app.core.response_streamer._stream_llm", multi_stream):
            from app.core.response_streamer import stream_chat_response
            await stream_chat_response(session_id, "What did I tell you?", mock_ws, seeded_user["user_id"])

        assert len(sent) > 0  # should still get a response
