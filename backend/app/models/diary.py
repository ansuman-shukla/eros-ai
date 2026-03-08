"""Diary entry document model."""

from datetime import datetime

from beanie import Document
from pydantic import Field


class DiaryEntry(Document):
    """A single diary entry written by the companion about the user.

    Written nightly by the Diary Writer Pipeline.
    Visibility gated by the user's diary page allowance (coin system).
    """

    user_id: str
    date: str  # ISO date string, e.g. "2024-11-21"
    content: str
    visible_to_user: bool = True
    page_number: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "diary_entries"
