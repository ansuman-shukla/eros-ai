"""Shared FastAPI dependencies for dependency injection."""

from fastapi import Depends, Header, HTTPException, status

from app.utils.jwt import decode_token
from app.models.user import User

from jose import JWTError


async def get_current_user(authorization: str = Header(default="")) -> User:
    """Decode the JWT from the Authorization header and return the user.

    Expected header format: `Bearer <token>`

    Raises:
        HTTPException(401): If token is missing, invalid, or user not found.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        user_id = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = await User.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
