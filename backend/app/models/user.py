"""User document model."""

from datetime import datetime

from beanie import Document
from pydantic import Field


class User(Document):
    """Represents a registered user."""

    email: str
    hashed_password: str
    name: str
    language: str = "en"
    active_trait_ids: list[str] = Field(default_factory=list)
    onboarding_complete: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
