"""Phase 5 — Filler generator unit tests."""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.voice.filler import generate_filler, DEFAULT_FILLER, FILLER_PROMPT_TEMPLATE
from app.models.user import User
from app.models.trait import Trait
from app.models.personality import PersonalityProfile


class TestFillerGenerator:
    """Tests for persona-shaped filler sentence generation."""

    async def test_filler_output_is_single_sentence(self, mock_redis):
        """Filler should be a single short sentence."""
        mock_response = MagicMock()
        mock_response.text = "Oh, that's a good question, let me think."

        with patch("app.voice.filler._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            filler = await generate_filler("sess_1", "What was my girlfriend's birthday?")
            assert filler == "Oh, that's a good question, let me think."
            assert len(filler.split()) <= 20

    async def test_filler_does_not_contain_partial_answer(self, mock_redis):
        """Filler should never reference specific facts or pretend to remember."""
        user = User(email="t@t.com", hashed_password="h", name="Test")
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        mock_response = MagicMock()
        mock_response.text = "Hmm, let me think about that for a sec."

        with patch("app.voice.filler._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            filler = await generate_filler("sess_2", "What did I say last week?", str(user.id))
            # Filler should not contain memory-like phrases
            assert "I remember" not in filler
            assert "last week" not in filler.lower()

    async def test_filler_tone_matches_bold_persona(self, mock_redis):
        """When user has a 'Bold' trait, filler prompt should include it."""
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

        mock_response = MagicMock()
        mock_response.text = "Alright, give me a second here."

        with patch("app.voice.filler._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            filler = await generate_filler("sess_3", "Tell me about my goals", str(user.id))

            # Verify the prompt sent to Gemini includes Bold persona
            call_args = mock_client.return_value.models.generate_content.call_args
            prompt_sent = call_args[1].get("contents") or call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("contents", "")
            assert "Bold" in str(prompt_sent)

    async def test_filler_tone_matches_gentle_persona(self, mock_redis):
        """When user has a 'Gentle' trait, filler prompt should include it."""
        trait = Trait(
            name="Gentle",
            category="warmth",
            prompt_modifier="You are gentle and nurturing.",
        )
        await trait.insert()

        user = User(
            email="t@t.com", hashed_password="h", name="Test",
            active_trait_ids=["Gentle"],
        )
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        mock_response = MagicMock()
        mock_response.text = "Oh, let me recall that for you, one moment."

        with patch("app.voice.filler._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            filler = await generate_filler("sess_4", "What's my dog's name?", str(user.id))

            call_args = mock_client.return_value.models.generate_content.call_args
            prompt_sent = call_args[1].get("contents") or call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("contents", "")
            assert "Gentle" in str(prompt_sent)

    async def test_filler_generated_with_no_persona_uses_default_tone(self, mock_redis):
        """Filler should work even without active persona traits."""
        user = User(
            email="t@t.com", hashed_password="h", name="Test",
            active_trait_ids=[],
        )
        await user.insert()
        await PersonalityProfile(user_id=str(user.id)).insert()

        mock_response = MagicMock()
        mock_response.text = "Let me think about that for a moment."

        with patch("app.voice.filler._get_client") as mock_client:
            mock_client.return_value.models.generate_content.return_value = mock_response
            filler = await generate_filler("sess_5", "Hello?", str(user.id))
            assert filler == "Let me think about that for a moment."

    async def test_filler_returns_default_on_api_error(self, mock_redis):
        """On Gemini API failure, return the safe default filler."""
        with patch("app.voice.filler._get_client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("API down")
            filler = await generate_filler("sess_err", "test query")
            assert filler == DEFAULT_FILLER
