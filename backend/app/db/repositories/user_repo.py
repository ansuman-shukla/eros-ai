"""User repository — database operations for users."""

from passlib.context import CryptContext

from app.models.user import User
from app.utils.errors import NotFoundError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a hash."""
    return pwd_context.verify(plain, hashed)


async def create_user(email: str, password: str, name: str) -> User:
    """Create a new user with a hashed password.

    Raises:
        ValueError: If a user with the same email already exists.
    """
    existing = await User.find_one(User.email == email)
    if existing:
        raise ValueError(f"User with email '{email}' already exists")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        name=name,
    )
    await user.insert()
    return user


async def get_user_by_email(email: str) -> User | None:
    """Find a user by email address."""
    return await User.find_one(User.email == email)


async def get_user_by_id(user_id: str) -> User | None:
    """Find a user by document ID."""
    return await User.get(user_id)
