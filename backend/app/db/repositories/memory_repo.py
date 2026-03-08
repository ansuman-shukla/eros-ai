"""Memory repository — database operations for hot and cold memories."""

from datetime import datetime

from app.models.memory import Memory, MemoryType
from app.utils.errors import NotFoundError


async def create_memory(user_id: str, data: dict) -> Memory:
    """Insert a new memory document."""
    memory = Memory(user_id=user_id, **data)
    await memory.insert()
    return memory


async def get_hot_memories(user_id: str) -> list[Memory]:
    """Return all hot memories for a user."""
    return await Memory.find(
        Memory.user_id == user_id, Memory.type == MemoryType.HOT
    ).to_list()


async def get_cold_memories(user_id: str) -> list[Memory]:
    """Return all cold memories for a user."""
    return await Memory.find(
        Memory.user_id == user_id, Memory.type == MemoryType.COLD
    ).to_list()


async def get_all_memories(user_id: str) -> list[Memory]:
    """Return all memories (hot + cold) for a user."""
    return await Memory.find(Memory.user_id == user_id).to_list()


async def update_memory(mem_id: str, updates: dict) -> Memory:
    """Partially update a memory document.

    Raises:
        NotFoundError: If the memory does not exist.
    """
    memory = await Memory.get(mem_id)
    if memory is None:
        raise NotFoundError("Memory", mem_id)

    for key, value in updates.items():
        if hasattr(memory, key):
            setattr(memory, key, value)

    memory.last_accessed = datetime.utcnow()
    await memory.save()
    return memory


async def delete_memory(mem_id: str) -> None:
    """Hard delete a memory document.

    Raises:
        NotFoundError: If the memory does not exist.
    """
    memory = await Memory.get(mem_id)
    if memory is None:
        raise NotFoundError("Memory", mem_id)

    await memory.delete()
