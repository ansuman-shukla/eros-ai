"""Phase 3 — Prompt builder, decision engine, and retrieval unit tests."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.prompt_builder import assemble_prompt, BASE_INSTRUCTIONS, MOOD_INFERENCE_BLOCK
from app.core.decision_engine import get_decision_token, _prepend_to_stream
from app.memory.retrieval import _parse_memory_ids
from app.models.user import User
from app.models.memory import Memory, MemoryType
from app.models.trait import Trait
from app.models.personality import PersonalityProfile
from app.db.redis_client import get_redis, session_prompt_key, session_hot_key


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _mock_stream(*tokens):
    """Create an async generator from a list of tokens."""
    for t in tokens:
        yield t


# ─── Prompt Builder Tests ────────────────────────────────────────────────────


class TestPromptBuilder:

    async def test_prompt_contains_hot_memory_name_field(self, mock_redis):
        """Hot memory name field should appear in the prompt."""
        user = User(email="t@t.com", hashed_password="h", name="Test")
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        # Put hot memory in Redis
        r = get_redis()
        await r.set(session_hot_key("sess_1", "name"), "Aryan")

        prompt = await assemble_prompt("sess_1", str(user.id))
        assert "name: Aryan" in prompt

    async def test_prompt_contains_persona_trait_modifier_text(self, mock_redis):
        """Active persona traits should inject their prompt modifiers."""
        trait = Trait(
            name="Bold",
            category="confidence",
            prompt_modifier="You are bold and direct.",
        )
        await trait.insert()

        user = User(
            email="t@t.com", hashed_password="h", name="Test",
            active_trait_ids=["Bold"],
        )
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        prompt = await assemble_prompt("sess_t", str(user.id))
        assert "bold and direct" in prompt.lower()

    async def test_prompt_contains_personality_type_summary(self, mock_redis):
        """Personality profile summary should be included when traits are strong."""
        user = User(email="t@t.com", hashed_password="h", name="Test")
        await user.insert()

        profile = PersonalityProfile(
            user_id=str(user.id),
            jungian_type="INFJ",
            type_confidence=0.8,
            trait_weights={"empathy": 0.9, "curiosity": 0.7, "humor": 0.1},
        )
        await profile.insert()

        prompt = await assemble_prompt("sess_p", str(user.id))
        assert "INFJ" in prompt
        assert "empathy" in prompt.lower()

    async def test_prompt_contains_mood_inference_block(self, mock_redis):
        """Mood inference instructions should always be present."""
        user = User(email="t@t.com", hashed_password="h", name="Test")
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        prompt = await assemble_prompt("sess_m", str(user.id))
        assert "Mood Awareness" in prompt

    async def test_prompt_stored_in_redis_after_assembly(self, mock_redis):
        """Assembled prompt should be cached in Redis."""
        user = User(email="t@t.com", hashed_password="h", name="Test")
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        await assemble_prompt("sess_r", str(user.id))

        r = get_redis()
        cached = await r.get(session_prompt_key("sess_r"))
        assert cached is not None
        assert "companion" in cached.lower()

    async def test_prompt_language_preference_applied(self, mock_redis):
        """Language preference should be in the prompt."""
        user = User(email="t@t.com", hashed_password="h", name="Test", language="hi")
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        prompt = await assemble_prompt("sess_l", str(user.id))
        assert "Respond in hi" in prompt


# ─── Decision Engine Tests ───────────────────────────────────────────────────


class TestDecisionEngine:

    async def test_decision_engine_returns_SEARCH_on_search_token(self):
        stream = _mock_stream("SEARCH", "\nHere is your answer")
        decision, remaining = await get_decision_token(stream)
        assert decision == "SEARCH"

    async def test_decision_engine_returns_NO_SEARCH_on_no_search_token(self):
        stream = _mock_stream("NO_SEARCH", "\nHello there!")
        decision, remaining = await get_decision_token(stream)
        assert decision == "NO_SEARCH"

    async def test_decision_engine_falls_through_on_unexpected_token(self):
        stream = _mock_stream("Hello! How", " are you?")
        decision, remaining = await get_decision_token(stream)
        assert decision == "NO_SEARCH"

    async def test_decision_engine_prepends_fallthrough_token_to_stream(self):
        stream = _mock_stream("Hello! How", " are you?")
        decision, remaining = await get_decision_token(stream)

        chunks = []
        async for chunk in remaining:
            chunks.append(chunk)

        # The first chunk should be prepended back
        assert "Hello! How" in chunks[0]
        assert " are you?" in chunks[1]


# ─── Retrieval Parser Tests ─────────────────────────────────────────────────


class TestRetrievalParser:

    def test_parse_valid_json_array(self):
        ids = _parse_memory_ids('["abc123", "def456"]')
        assert ids == ["abc123", "def456"]

    def test_parse_empty_array(self):
        ids = _parse_memory_ids("[]")
        assert ids == []

    def test_parse_with_code_fences(self):
        ids = _parse_memory_ids('```json\n["id1"]\n```')
        assert ids == ["id1"]

    def test_parse_invalid_json_returns_empty(self):
        ids = _parse_memory_ids("not json at all")
        assert ids == []


# ─── Retrieval E2E Tests (mocked Gemini) ─────────────────────────────────────


class TestRetrieval:

    async def test_retrieval_empty_cold_memory_returns_empty_list(self, mock_redis):
        """No cold memories should return empty without calling Gemini."""
        from app.memory.retrieval import retrieve_relevant_memories
        result = await retrieve_relevant_memories("no_cold_session", "what's my name?")
        assert result == []

    async def test_retrieval_gemini_error_returns_empty_not_exception(self, mock_redis):
        """Gemini errors should be caught — return empty, not crash."""
        from app.memory.retrieval import retrieve_relevant_memories
        from app.memory.cold_memory import load_cold_to_redis

        await Memory(
            user_id="usr_1", type=MemoryType.COLD, content="Some memory"
        ).insert()
        await load_cold_to_redis("sess_err", "usr_1")

        with patch("app.memory.retrieval.get_gemini_client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("API error")
            result = await retrieve_relevant_memories("sess_err", "test query")
            assert result == []

    async def test_retrieval_resolves_returned_ids_from_redis(self, mock_redis):
        """Valid IDs from Gemini should resolve to memory entries."""
        from app.memory.retrieval import retrieve_relevant_memories
        from app.memory.cold_memory import load_cold_to_redis

        mem = await Memory(
            user_id="usr_1", type=MemoryType.COLD, content="Met girlfriend on Oct 3rd"
        ).insert()
        await load_cold_to_redis("sess_resolve", "usr_1")

        mock_response = MagicMock()
        mock_response.text = json.dumps([str(mem.id)])

        with patch("app.memory.retrieval.get_gemini_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            result = await retrieve_relevant_memories("sess_resolve", "when did I meet my gf?")
            assert len(result) == 1
            assert result[0]["content"] == "Met girlfriend on Oct 3rd"

    async def test_retrieval_skips_invalid_ids_gracefully(self, mock_redis):
        """Invalid IDs from Gemini should be skipped, not crash."""
        from app.memory.retrieval import retrieve_relevant_memories
        from app.memory.cold_memory import load_cold_to_redis

        await Memory(
            user_id="usr_1", type=MemoryType.COLD, content="Real memory"
        ).insert()
        await load_cold_to_redis("sess_skip", "usr_1")

        mock_response = MagicMock()
        mock_response.text = json.dumps(["nonexistent_id_123"])

        with patch("app.memory.retrieval.get_gemini_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            result = await retrieve_relevant_memories("sess_skip", "test")
            assert result == []
