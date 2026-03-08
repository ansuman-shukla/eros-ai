"""JWT token encoding and decoding utilities."""

from datetime import datetime, timedelta

from jose import jwt, JWTError

from app.config import settings


def encode_token(user_id: str) -> str:
    """Create a JWT access token for the given user ID.

    Args:
        user_id: The user's document ID to embed in the token.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> str:
    """Decode a JWT access token and return the user ID.

    Args:
        token: Encoded JWT string.

    Returns:
        The user ID (sub claim).

    Raises:
        JWTError: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise JWTError("Token missing 'sub' claim")

    return user_id
