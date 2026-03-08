"""Phase 5 — Voice flow integration tests.

Tests cover the full voice pipeline via HTTP endpoints:
- Voice token endpoint (session init + token issuance)
- Internal voice-turn endpoint (decision engine + response)
- Internal voice-interrupt endpoint (marking turns as interrupted)
"""

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from httpx import AsyncClient

from app.models.session import Session
from app.models.user import User
from app.models.personality import PersonalityProfile
from app.models.coins import CoinLedger
from app.models.memory import Memory, MemoryType


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _mock_stream(*tokens):
    """Create an async generator yielding tokens."""
    for t in tokens:
        yield t


def _mock_livekit_token():
    """Patch the LiveKit AccessToken to return a mock JWT."""
    mock_chain = MagicMock()
    mock_chain.with_identity.return_value = mock_chain
    mock_chain.with_name.return_value = mock_chain
    mock_chain.with_grants.return_value = mock_chain
    mock_chain.with_ttl.return_value = mock_chain
    mock_chain.to_jwt.return_value = "mocked_livekit_jwt"
    return mock_chain


# ─── Token Endpoint Tests ───────────────────────────────────────────────────


class TestVoiceTokenEndpoint:

    async def test_voice_token_endpoint_returns_session_id_and_token(
        self, client: AsyncClient, seeded_user
    ):
        """POST /api/v1/voice/token should return session_id, livekit_token, room_name."""
        with patch("app.voice.token_service.AccessToken", return_value=_mock_livekit_token()):
            resp = await client.post(
                "/api/v1/voice/token",
                headers={"Authorization": f"Bearer {seeded_user['token']}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "livekit_token" in data
        assert "room_name" in data
        assert data["livekit_token"] == "mocked_livekit_jwt"
        assert data["room_name"].startswith("companion-")

    async def test_voice_token_endpoint_initializes_session_in_mongo(
        self, client: AsyncClient, seeded_user
    ):
        """Voice session should be created in MongoDB with mode='voice'."""
        with patch("app.voice.token_service.AccessToken", return_value=_mock_livekit_token()):
            resp = await client.post(
                "/api/v1/voice/token",
                headers={"Authorization": f"Bearer {seeded_user['token']}"},
            )

        data = resp.json()
        session = await Session.get(data["session_id"])
        assert session is not None
        assert session.mode == "voice"
        assert session.status == "active"

    async def test_voice_token_requires_auth(self, client: AsyncClient):
        """Token endpoint should reject unauthenticated requests."""
        resp = await client.post("/api/v1/voice/token")
        assert resp.status_code in (401, 403, 422)


# ─── Internal Voice Turn Tests ──────────────────────────────────────────────


class TestInternalVoiceTurnEndpoint:

    async def _setup_voice_session(self, client: AsyncClient, seeded_user) -> str:
        """Helper: create a voice session and return session_id."""
        with patch("app.voice.token_service.AccessToken", return_value=_mock_livekit_token()):
            resp = await client.post(
                "/api/v1/voice/token",
                headers={"Authorization": f"Bearer {seeded_user['token']}"},
            )
        return resp.json()["session_id"]

    async def test_internal_voice_turn_no_search_returns_response_no_filler(
        self, client: AsyncClient, seeded_user
    ):
        """NO_SEARCH path should return response_text with no filler."""
        session_id = await self._setup_voice_session(client, seeded_user)

        with patch("app.api.v1.voice._stream_llm") as mock_llm:
            mock_llm.return_value = _mock_stream("NO_SEARCH", "\nHey! How are you?")
            resp = await client.post(
                "/api/v1/voice/internal/voice-turn",
                json={"session_id": session_id, "transcript_text": "Hello!"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "Hey! How are you?" in data["response_text"]
        assert data["filler_text"] is None
        assert data["memory_used"] is False

    async def test_internal_voice_turn_search_returns_filler_and_response(
        self, client: AsyncClient, seeded_user
    ):
        """SEARCH path should return both filler_text and response_text."""
        session_id = await self._setup_voice_session(client, seeded_user)

        with (
            patch("app.api.v1.voice._stream_llm") as mock_llm,
            patch("app.api.v1.voice.generate_filler") as mock_filler,
            patch("app.api.v1.voice.retrieve_relevant_memories") as mock_memories,
        ):
            # First stream: decision = SEARCH
            # Second stream: actual response after enrichment
            mock_llm.side_effect = [
                _mock_stream("SEARCH"),
                _mock_stream("Yes! You met her at the park."),
            ]
            mock_filler.return_value = "Hmm, let me think..."
            mock_memories.return_value = [{"content": "Met girlfriend at park"}]

            resp = await client.post(
                "/api/v1/voice/internal/voice-turn",
                json={"session_id": session_id, "transcript_text": "Where did I meet my girlfriend?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filler_text"] == "Hmm, let me think..."
        assert "park" in data["response_text"].lower()
        assert data["memory_used"] is True

    async def test_internal_voice_turn_search_memory_used_flag_true(
        self, client: AsyncClient, seeded_user
    ):
        """memory_used flag should be True when memories are retrieved."""
        session_id = await self._setup_voice_session(client, seeded_user)

        with (
            patch("app.api.v1.voice._stream_llm") as mock_llm,
            patch("app.api.v1.voice.generate_filler") as mock_filler,
            patch("app.api.v1.voice.retrieve_relevant_memories") as mock_memories,
        ):
            mock_llm.side_effect = [
                _mock_stream("SEARCH"),
                _mock_stream("Here is what I recall."),
            ]
            mock_filler.return_value = "One sec..."
            mock_memories.return_value = [{"content": "Some memory"}]

            resp = await client.post(
                "/api/v1/voice/internal/voice-turn",
                json={"session_id": session_id, "transcript_text": "Tell me about last week"},
            )

        data = resp.json()
        assert data["memory_used"] is True

    async def test_voice_turn_persists_turns_to_session(
        self, client: AsyncClient, seeded_user
    ):
        """User and agent turns should be persisted in the session document."""
        session_id = await self._setup_voice_session(client, seeded_user)

        with patch("app.api.v1.voice._stream_llm") as mock_llm:
            mock_llm.return_value = _mock_stream("NO_SEARCH", "\nHello there!")
            await client.post(
                "/api/v1/voice/internal/voice-turn",
                json={"session_id": session_id, "transcript_text": "Hi!"},
            )

        session = await Session.get(session_id)
        assert len(session.turns) == 2
        assert session.turns[0].role == "user"
        assert session.turns[0].mode == "voice"
        assert session.turns[1].role == "agent"


# ─── Internal Interrupt Tests ───────────────────────────────────────────────


class TestInternalVoiceInterruptEndpoint:

    async def test_interruption_marks_turn_as_interrupted_in_mongo(
        self, client: AsyncClient, seeded_user
    ):
        """POST /internal/voice-interrupt should mark a turn as interrupted."""
        # Setup: create session with one turn pair
        with patch("app.voice.token_service.AccessToken", return_value=_mock_livekit_token()):
            resp = await client.post(
                "/api/v1/voice/token",
                headers={"Authorization": f"Bearer {seeded_user['token']}"},
            )
        session_id = resp.json()["session_id"]

        # Add a turn pair manually
        with patch("app.api.v1.voice._stream_llm") as mock_llm:
            mock_llm.return_value = _mock_stream("NO_SEARCH", "\nHello!")
            await client.post(
                "/api/v1/voice/internal/voice-turn",
                json={"session_id": session_id, "transcript_text": "Hey"},
            )

        # Mark agent turn (turn_id=2) as interrupted
        resp = await client.post(
            "/api/v1/voice/internal/voice-interrupt",
            json={"session_id": session_id, "turn_id": 2},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify in MongoDB
        session = await Session.get(session_id)
        agent_turn = next(t for t in session.turns if t.turn_id == 2)
        assert agent_turn.interrupted is True

    async def test_interrupt_nonexistent_turn_returns_404(
        self, client: AsyncClient, seeded_user
    ):
        """Interrupting a turn that doesn't exist should return 404."""
        with patch("app.voice.token_service.AccessToken", return_value=_mock_livekit_token()):
            resp = await client.post(
                "/api/v1/voice/token",
                headers={"Authorization": f"Bearer {seeded_user['token']}"},
            )
        session_id = resp.json()["session_id"]

        resp = await client.post(
            "/api/v1/voice/internal/voice-interrupt",
            json={"session_id": session_id, "turn_id": 999},
        )
        assert resp.status_code == 404
