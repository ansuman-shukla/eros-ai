"""ARQ worker pool initialization."""

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings

_pool = None


async def get_arq_pool():
    """Get or create the ARQ connection pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.ARQ_REDIS_URL))
    return _pool
