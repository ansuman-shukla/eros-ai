"""Phase 5 — Voice token service unit tests."""

from unittest.mock import patch, MagicMock
from datetime import timedelta

import pytest


class TestVoiceTokenService:
    """Tests for LiveKit AccessToken generation."""

    def test_livekit_token_generated_with_correct_room_name(self):
        """Token should contain room name matching companion-{session_id}."""
        with patch("app.voice.token_service.AccessToken") as MockAccessToken:
            mock_token = MagicMock()
            mock_chain = MagicMock()
            mock_chain.with_identity.return_value = mock_chain
            mock_chain.with_name.return_value = mock_chain
            mock_chain.with_grants.return_value = mock_chain
            mock_chain.with_ttl.return_value = mock_chain
            mock_chain.to_jwt.return_value = "mock_jwt_token"
            MockAccessToken.return_value = mock_chain

            from app.voice.token_service import generate_room_token, get_room_name

            token = generate_room_token("user_123", "session_abc")

            # Verify with_grants was called with room matching convention
            call_args = mock_chain.with_grants.call_args
            grants = call_args[0][0]
            assert grants.room == "companion-session_abc"
            assert grants.room_join is True

            # Verify room name helper
            assert get_room_name("session_abc") == "companion-session_abc"

    def test_livekit_token_contains_user_identity(self):
        """Token should set participant identity to user_id."""
        with patch("app.voice.token_service.AccessToken") as MockAccessToken:
            mock_chain = MagicMock()
            mock_chain.with_identity.return_value = mock_chain
            mock_chain.with_name.return_value = mock_chain
            mock_chain.with_grants.return_value = mock_chain
            mock_chain.with_ttl.return_value = mock_chain
            mock_chain.to_jwt.return_value = "mock_jwt_token"
            MockAccessToken.return_value = mock_chain

            from app.voice.token_service import generate_room_token

            generate_room_token("user_xyz", "session_123")

            # Verify with_identity was called with user_id
            mock_chain.with_identity.assert_called_once_with("user_xyz")
            mock_chain.with_name.assert_called_once_with("user-user_xyz")
