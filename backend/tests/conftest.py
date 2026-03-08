"""Shared test fixtures for the Companion AI test suite."""

import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fakeredis import aioredis as fakeredis
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from app.db import redis_client
from app.db.mongodb import ALL_MODELS


# ─── Event loop ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── Database (mongomock — no real MongoDB needed) ───────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Initialize Beanie with an in-memory mock MongoDB for each test."""
    client = AsyncMongoMockClient()
    db = client["companion_ai_test"]
    await init_beanie(database=db, document_models=ALL_MODELS)
    yield
    # mongomock is in-memory, no cleanup needed — each test gets a fresh client


# ─── Redis (fakeredis — no real Redis needed) ────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def mock_redis():
    """Replace the real Redis client with fakeredis for all tests."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    redis_client.pool = fake
    yield fake
    await fake.aclose()
    redis_client.pool = None


# ─── HTTP Client ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Seeded User ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seeded_user(client: AsyncClient):
    """Create a test user and return their data with JWT.

    Returns:
        dict: {"user_id": ..., "token": ..., "email": ..., "name": ...}
    """
    # Create user directly via models (auth routes may not exist yet)
    from app.models.user import User
    from app.models.coins import CoinLedger
    from app.models.personality import PersonalityProfile
    from app.utils.jwt import encode_token
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user = User(
        email="test@example.com",
        hashed_password=pwd_context.hash("TestPassword123!"),
        name="Test User",
    )
    await user.insert()

    ledger = CoinLedger(user_id=str(user.id))
    await ledger.insert()

    profile = PersonalityProfile(user_id=str(user.id))
    await profile.insert()

    token = encode_token(str(user.id))

    return {
        "user_id": str(user.id),
        "token": token,
        "email": "test@example.com",
        "name": "Test User",
    }
