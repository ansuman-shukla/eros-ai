"""Coins repository — earning and spending operations.

This module is created in Phase 3 because the response streamer needs
to award coins after each message. Full coin API routes come in Phase 4.
"""

from datetime import date, datetime
from app.models.coins import CoinLedger
from app.utils.errors import InsufficientCoinsError
from app.utils.logger import get_logger

logger = get_logger(__name__)

COINS_PER_MESSAGE = 10
DAILY_CAP = 100
DIARY_PAGE_COST = 50


async def award_coins(user_id: str, amount: int = COINS_PER_MESSAGE) -> int:
    """Award coins to a user for a chat interaction.

    Enforces the daily cap (100 coins/day). Resets if the date changed.

    Args:
        user_id: User document ID.
        amount: Coins to award (default: 10 per message).

    Returns:
        Number of coins actually awarded (may be less due to cap).
    """
    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    if ledger is None:
        logger.warning(f"No CoinLedger for user {user_id}")
        return 0

    today = date.today().isoformat()

    # Reset daily counter if date changed
    if ledger.last_reset_date != today:
        ledger.daily_earned_today = 0
        ledger.last_reset_date = today

    # Enforce daily cap
    remaining = ledger.daily_cap - ledger.daily_earned_today
    actual = min(amount, remaining)

    if actual <= 0:
        logger.info(f"User {user_id} hit daily coin cap")
        return 0

    ledger.total_coins += actual
    ledger.daily_earned_today += actual
    ledger.last_updated = datetime.utcnow()
    await ledger.save()

    logger.info(f"Awarded {actual} coins to user {user_id} (total: {ledger.total_coins})")
    return actual


async def spend_coins(user_id: str, amount: int) -> int:
    """Spend coins from a user's balance.

    Args:
        user_id: User document ID.
        amount: Coins to spend.

    Returns:
        Remaining balance after spending.

    Raises:
        InsufficientCoinsError: If user doesn't have enough coins.
    """
    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    if ledger is None:
        raise InsufficientCoinsError(required=amount, available=0)

    if ledger.total_coins < amount:
        raise InsufficientCoinsError(required=amount, available=ledger.total_coins)

    ledger.total_coins -= amount
    ledger.last_updated = datetime.utcnow()
    await ledger.save()

    return ledger.total_coins


async def purchase_diary_page(user_id: str) -> dict:
    """Purchase a diary page with coins.

    Returns:
        Dict with remaining coins and total pages owned.
    """
    remaining = await spend_coins(user_id, DIARY_PAGE_COST)

    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    ledger.diary_pages_owned += 1
    await ledger.save()

    return {
        "remaining_coins": remaining,
        "diary_pages_owned": ledger.diary_pages_owned,
    }


async def get_balance(user_id: str) -> dict:
    """Get coin balance for a user."""
    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    if ledger is None:
        return {"total_coins": 0, "daily_earned_today": 0, "diary_pages_owned": 0}

    return {
        "total_coins": ledger.total_coins,
        "daily_earned_today": ledger.daily_earned_today,
        "daily_cap": ledger.daily_cap,
        "diary_pages_owned": ledger.diary_pages_owned,
    }


async def reset_daily_earned(user_id: str) -> None:
    """Reset the daily earned counter (called at midnight cron)."""
    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    if ledger:
        ledger.daily_earned_today = 0
        ledger.last_reset_date = date.today().isoformat()
        await ledger.save()
