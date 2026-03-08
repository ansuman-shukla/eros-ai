"""Phase 1 — Auth unit tests."""

import pytest
from datetime import datetime, timedelta

from jose import jwt, JWTError

from app.utils.jwt import encode_token, decode_token
from app.db.repositories.user_repo import hash_password, verify_password
from app.config import settings


class TestJWT:
    """Tests for JWT token encoding and decoding."""

    def test_encode_and_decode_token_roundtrip(self):
        """Encoding then decoding should return the same user_id."""
        user_id = "usr_12345"
        token = encode_token(user_id)
        decoded = decode_token(token)
        assert decoded == user_id

    def test_expired_token_raises_error(self):
        """An expired token should raise JWTError."""
        expire = datetime.utcnow() - timedelta(minutes=5)
        token = jwt.encode(
            {"sub": "usr_1", "exp": expire},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_invalid_token_signature_raises_error(self):
        """A token signed with a different key should raise JWTError."""
        token = jwt.encode(
            {"sub": "usr_1", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret-key",
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(JWTError):
            decode_token(token)


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_password_hashing_not_stored_as_plaintext(self):
        """Hashed password should not equal the plaintext."""
        plain = "SuperSecret123!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert len(hashed) > 20

    def test_password_verification_correct_returns_true(self):
        """Correct password should verify successfully."""
        plain = "SuperSecret123!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_password_verification_wrong_returns_false(self):
        """Wrong password should fail verification."""
        hashed = hash_password("CorrectPassword")
        assert verify_password("WrongPassword", hashed) is False
