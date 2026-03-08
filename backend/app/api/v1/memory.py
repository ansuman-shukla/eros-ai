"""Memory API routes — CRUD endpoints (debug/admin)."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.memory import MemoryCreateRequest, MemoryUpdateRequest, MemoryResponse
from app.db.repositories import memory_repo

router = APIRouter()


@router.get("/hot", response_model=list[MemoryResponse])
async def get_hot_memories(user: User = Depends(get_current_user)):
    """List all hot memories for the current user."""
    memories = await memory_repo.get_hot_memories(str(user.id))
    return [
        MemoryResponse(id=str(m.id), user_id=m.user_id, type=m.type.value,
                        field=m.field, content=m.content, tag=m.tag,
                        subtype=m.subtype, entities=m.entities,
                        emotional_weight=m.emotional_weight)
        for m in memories
    ]


@router.get("/cold", response_model=list[MemoryResponse])
async def get_cold_memories(user: User = Depends(get_current_user)):
    """List all cold memories for the current user."""
    memories = await memory_repo.get_cold_memories(str(user.id))
    return [
        MemoryResponse(id=str(m.id), user_id=m.user_id, type=m.type.value,
                        field=m.field, content=m.content, tag=m.tag,
                        subtype=m.subtype, entities=m.entities,
                        emotional_weight=m.emotional_weight)
        for m in memories
    ]


@router.post("/", response_model=MemoryResponse, status_code=201)
async def create_memory(body: MemoryCreateRequest, user: User = Depends(get_current_user)):
    """Create a new memory (hot or cold)."""
    m = await memory_repo.create_memory(str(user.id), body.model_dump())
    return MemoryResponse(
        id=str(m.id), user_id=m.user_id, type=m.type.value,
        field=m.field, content=m.content, tag=m.tag,
        subtype=m.subtype, entities=m.entities,
        emotional_weight=m.emotional_weight,
    )


@router.patch("/{mem_id}", response_model=MemoryResponse)
async def update_memory(mem_id: str, body: MemoryUpdateRequest, user: User = Depends(get_current_user)):
    """Update an existing memory."""
    updates = body.model_dump(exclude_none=True)
    m = await memory_repo.update_memory(mem_id, updates)
    return MemoryResponse(
        id=str(m.id), user_id=m.user_id, type=m.type.value,
        field=m.field, content=m.content, tag=m.tag,
        subtype=m.subtype, entities=m.entities,
        emotional_weight=m.emotional_weight,
    )


@router.delete("/{mem_id}", status_code=204)
async def delete_memory(mem_id: str, user: User = Depends(get_current_user)):
    """Delete a memory."""
    await memory_repo.delete_memory(mem_id)
