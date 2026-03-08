"""Coin ledger document model — tracks earning and spending."""

from datetime import datetime

from beanie import Document
from pydantic import Field


class CoinLedger(Document):
    """Tracks a user's coin balance, daily earning, and diary page ownership.

    Earning rules:
    - 10 coins per normal message, capped at 100/day.
    Spending:
    - 50 coins per diary page unlock.
    - Variable per trait unlock.
    """

    user_id: str
    total_coins: int = 0
    daily_earned_today: int = 0
    daily_cap: int = 100
    diary_pages_owned: int = 5  # starting allocation
    last_reset_date: str | None = None  # ISO date string
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "coin_ledger"
