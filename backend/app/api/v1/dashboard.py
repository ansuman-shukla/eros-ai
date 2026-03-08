"""Dashboard API routes — read-only endpoints for the frontend dashboard.

All endpoints require JWT authentication.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.models.user import User
from app.models.personality import PersonalityProfile
from app.models.session import Session
from app.models.diary import DiaryEntry
from app.models.trait import Trait
from app.models.coins import CoinLedger
from app.schemas.dashboard import (
    PersonalityResponse,
    ActivityResponse,
    DayActivity,
    DiaryListResponse,
    DiaryEntryResponse,
    TraitLibraryResponse,
    TraitResponse,
)
from app.utils.errors import NotFoundError
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ─── GET /personality ────────────────────────────────────────────────────────


@router.get("/personality", response_model=PersonalityResponse)
async def get_personality(user: User = Depends(get_current_user)):
    """Return the user's full personality profile."""
    user_id = str(user.id)

    profile = await PersonalityProfile.find_one(
        PersonalityProfile.user_id == user_id
    )
    if not profile:
        raise NotFoundError("PersonalityProfile", user_id)

    return PersonalityResponse(
        user_id=user_id,
        jungian_type=profile.jungian_type,
        type_confidence=profile.type_confidence,
        archetypes=profile.archetypes,
        trait_weights=profile.trait_weights,
        attachment_style=profile.attachment_style,
        cognitive_style=profile.cognitive_style,
        core_values=profile.core_values,
        version=profile.version,
        last_updated=profile.last_updated,
    )


# ─── GET /activity ───────────────────────────────────────────────────────────


@router.get("/activity", response_model=ActivityResponse)
async def get_activity(
    days: int = Query(default=30, ge=1, le=90),
    user: User = Depends(get_current_user),
):
    """Return per-day session/turn counts for the last N days."""
    user_id = str(user.id)
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Fetch all sessions started after cutoff
    sessions = await Session.find(
        Session.user_id == user_id,
        Session.started_at >= cutoff,
    ).to_list()

    # Aggregate by date
    day_map: dict[str, DayActivity] = defaultdict(
        lambda: DayActivity(date="")
    )

    total_sessions = 0
    total_turns = 0

    for session in sessions:
        date_str = session.started_at.strftime("%Y-%m-%d")
        day = day_map[date_str]
        day.date = date_str
        day.session_count += 1
        total_sessions += 1

        for turn in session.turns:
            day.turn_count += 1
            total_turns += 1
            if turn.mode == "chat":
                day.chat_turns += 1
            elif turn.mode == "voice":
                day.voice_turns += 1

    # Sort by date descending
    sorted_days = sorted(day_map.values(), key=lambda d: d.date, reverse=True)

    return ActivityResponse(
        user_id=user_id,
        days=sorted_days,
        total_sessions=total_sessions,
        total_turns=total_turns,
    )


# ─── GET /diary ──────────────────────────────────────────────────────────────


@router.get("/diary", response_model=DiaryListResponse)
async def get_diary(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Return visible diary entries, paginated.

    Only entries where visible_to_user=True are returned.
    Entries are sorted by date descending (newest first).
    """
    user_id = str(user.id)

    # Get coin ledger for pages_owned count
    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    pages_owned = ledger.diary_pages_owned if ledger else 5

    # Count total visible entries
    total = await DiaryEntry.find(
        DiaryEntry.user_id == user_id,
        DiaryEntry.visible_to_user == True,  # noqa: E712
    ).count()

    # Fetch paginated entries, sorted by date descending
    skip = (page - 1) * page_size
    entries = await DiaryEntry.find(
        DiaryEntry.user_id == user_id,
        DiaryEntry.visible_to_user == True,  # noqa: E712
    ).sort("-date").skip(skip).limit(page_size).to_list()

    return DiaryListResponse(
        entries=[
            DiaryEntryResponse(
                id=str(entry.id),
                date=entry.date,
                content=entry.content,
                page_number=entry.page_number,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
        total=total,
        pages_owned=pages_owned,
        page=page,
        page_size=page_size,
    )


# ─── GET /traits ─────────────────────────────────────────────────────────────


@router.get("/traits", response_model=TraitLibraryResponse)
async def get_traits(user: User = Depends(get_current_user)):
    """Return the full trait library with active flags for the user."""
    active_ids = user.active_trait_ids or []

    # Fetch all traits from the library
    all_traits = await Trait.find_all().to_list()

    return TraitLibraryResponse(
        traits=[
            TraitResponse(
                id=str(trait.id),
                name=trait.name,
                category=trait.category,
                prompt_modifier=trait.prompt_modifier,
                coin_cost=trait.coin_cost,
                locked=trait.locked,
                is_active=trait.name in active_ids,
            )
            for trait in all_traits
        ],
        active_trait_ids=active_ids,
    )
