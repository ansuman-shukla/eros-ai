"""MongoDB / Beanie initialization."""

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.config import settings
from app.models.user import User
from app.models.memory import Memory
from app.models.session import Session
from app.models.personality import PersonalityProfile
from app.models.diary import DiaryEntry
from app.models.coins import CoinLedger
from app.models.trait import Trait

client: AsyncIOMotorClient | None = None

ALL_MODELS = [User, Memory, Session, PersonalityProfile, DiaryEntry, CoinLedger, Trait]


async def init_db(db_name: str | None = None):
    """Initialize Beanie with all document models.

    Args:
        db_name: Override database name (used in tests).
    """
    global client
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[db_name or settings.MONGODB_DB]
    await init_beanie(database=db, document_models=ALL_MODELS)


async def close_db():
    """Close the MongoDB client connection."""
    global client
    if client:
        client.close()
        client = None
