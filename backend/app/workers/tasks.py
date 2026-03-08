"""ARQ worker task definitions — now wired to real pipelines."""

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def memory_curation_job(ctx: dict, session_id: str):
    """Extract and reconcile memories from a completed session."""
    from app.pipelines.memory_curation import run_memory_curation
    result = await run_memory_curation(session_id)
    logger.info(f"Memory curation job finished: {result}")
    return result


async def personality_update_job(ctx: dict, session_id: str):
    """Compute and apply personality trait deltas from a completed session."""
    from app.pipelines.personality_update import run_personality_update
    result = await run_personality_update(session_id)
    logger.info(f"Personality update job finished: {result}")
    return result


async def diary_writer_job(ctx: dict, user_id: str, date: str):
    """Generate the companion's daily diary entry about the user."""
    from app.pipelines.diary_writer import run_diary_writer
    result = await run_diary_writer(user_id, date)
    logger.info(f"Diary writer job finished: {result}")
    return result


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [memory_curation_job, personality_update_job, diary_writer_job]
    # cron_jobs added when ARQ cron support is configured

