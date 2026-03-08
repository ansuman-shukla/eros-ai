"""Coin system API routes."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.db.repositories import coins_repo

router = APIRouter()


@router.get("/balance")
async def get_balance(user: User = Depends(get_current_user)):
    """Get current coin balance and stats."""
    return await coins_repo.get_balance(str(user.id))


@router.post("/buy-diary-page")
async def buy_diary_page(user: User = Depends(get_current_user)):
    """Purchase a diary page for 50 coins.

    Reveals previously locked diary entries at the new page number.
    """
    from app.models.diary import DiaryEntry

    result = await coins_repo.purchase_diary_page(str(user.id))

    # Reveal any diary entry at the newly purchased page
    entry = await DiaryEntry.find_one(
        DiaryEntry.user_id == str(user.id),
        DiaryEntry.page_number == result["diary_pages_owned"],
    )
    if entry and not entry.visible_to_user:
        entry.visible_to_user = True
        await entry.save()

    return result
