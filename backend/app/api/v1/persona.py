"""Persona API routes — update active personality traits.

Separated from dashboard to keep write operations in their own module.
"""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.dashboard import (
    UpdateActiveTraitsRequest,
    UpdateActiveTraitsResponse,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.patch("/active", response_model=UpdateActiveTraitsResponse)
async def update_active_traits(
    body: UpdateActiveTraitsRequest,
    user: User = Depends(get_current_user),
):
    """Update the user's active persona trait IDs.

    Replaces all active traits with the provided list.
    Trait names must correspond to existing Trait documents.
    """
    user.active_trait_ids = body.active_trait_ids
    await user.save()

    logger.info(
        f"Active traits updated for user {user.id}: {body.active_trait_ids}"
    )

    return UpdateActiveTraitsResponse(
        active_trait_ids=body.active_trait_ids,
    )
