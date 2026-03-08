"""Diary writer pipeline — generates end-of-day diary entries from session transcripts.

Runs as an EOD cron job. Aggregates all sessions for a user on a given day,
generates a diary entry via Gemini, and determines visibility based on page ownership.
"""

import json
from datetime import datetime, date, timedelta

from google import genai

from app.config import settings
from app.models.session import Session
from app.models.diary import DiaryEntry
from app.models.coins import CoinLedger
from app.pipelines.memory_curation import format_transcript
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


DIARY_PROMPT = """You are writing a personal diary entry in the FIRST PERSON from the perspective of an AI companion, reflecting on today's conversations with the user.

## Today's Conversations
{transcript}

## Instructions
Write a warm, introspective diary entry (150-300 words) that:
- Reflects on the key topics discussed today
- Notes any emotional shifts or important moments
- Shows genuine care for the user
- Uses a personal, intimate tone (like writing in your own diary)
- References specific details from the conversations
- Ends with a forward-looking thought

Do NOT use bullet points. Write in flowing paragraphs.
Do NOT mention being an AI. Write as if you are a person reflecting on your day with someone you care about.
"""


async def aggregate_day_transcript(user_id: str, target_date: str) -> str:
    """Aggregate all session turns for a user on a given date.

    Args:
        user_id: User document ID.
        target_date: ISO date string (YYYY-MM-DD).

    Returns:
        Combined transcript from all sessions that day.
    """
    dt = datetime.fromisoformat(target_date)
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    sessions = await Session.find(
        Session.user_id == user_id,
        Session.started_at >= start,
        Session.started_at < end,
    ).to_list()

    if not sessions:
        return ""

    all_turns = []
    for session in sessions:
        all_turns.extend(session.turns)

    return format_transcript(all_turns)


async def generate_diary_entry(transcript: str) -> str:
    """Generate a diary entry from the day's transcript via Gemini."""
    client = _get_client()
    prompt = DIARY_PROMPT.format(transcript=transcript)

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Diary generation failed: {e}")
        return ""


async def determine_visibility(user_id: str, page_number: int) -> bool:
    """Check if a diary page should be visible based on user's page ownership."""
    ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
    if ledger is None:
        return False
    return page_number <= ledger.diary_pages_owned


async def run_diary_writer(user_id: str, target_date: str) -> dict:
    """Full diary writer pipeline for a user on a given date.

    Called as an EOD cron job.

    Args:
        user_id: User document ID.
        target_date: ISO date string (YYYY-MM-DD).

    Returns:
        Result dict with entry info or skip reason.
    """
    transcript = await aggregate_day_transcript(user_id, target_date)
    if not transcript:
        logger.info(f"No sessions for user {user_id} on {target_date}, skipping diary")
        return {"skipped": True, "reason": "no sessions today"}

    content = await generate_diary_entry(transcript)
    if not content:
        return {"skipped": True, "reason": "generation failed"}

    # Determine page number
    existing_count = await DiaryEntry.find(DiaryEntry.user_id == user_id).count()
    page_number = existing_count + 1

    # Determine visibility
    visible = await determine_visibility(user_id, page_number)

    entry = DiaryEntry(
        user_id=user_id,
        date=target_date,
        content=content,
        visible_to_user=visible,
        page_number=page_number,
    )
    await entry.insert()

    logger.info(
        f"Diary entry #{page_number} written for user {user_id} "
        f"(visible={visible})"
    )
    return {
        "entry_id": str(entry.id),
        "page_number": page_number,
        "visible": visible,
    }
