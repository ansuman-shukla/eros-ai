"""Memory curation pipeline — extracts and reconciles memories from session transcripts.

Two-pass Gemini-powered pipeline:
  Pass 1: Extract raw memory candidates from transcript
  Pass 2: Reconcile candidates against existing memories → diff (add/update/delete)
"""

import json
from datetime import datetime, timedelta

from google import genai

from app.config import settings
from app.models.session import Session
from app.models.memory import Memory
from app.db.repositories import memory_repo
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


EXTRACTION_PROMPT = """You are a memory extraction system. Analyze the following conversation transcript and extract factual information the user reveals about themselves.

## Transcript
{transcript}

## Instructions
Extract memories in these categories:
- **hot** (always-in-prompt facts): name, age, gender, location, occupation, relationship status, native language, preferences
- **cold** (on-demand facts): events, experiences, opinions, relationships, goals, fears, habits, health info

For each memory, return a JSON object with:
- "type": "hot" or "cold"
- "field": (for hot only) the field name like "name", "age", etc.
- "content": the factual information
- "subtype": (for cold only) one of: relationship_event, career_event, health_info, personal_preference, daily_context, emotional_event, goal, opinion
- "entities": list of people/places/things mentioned
- "emotional_weight": 0.0-1.0 how emotionally significant this is

IMPORTANT:
- Only extract information the USER said, not the agent.
- Ignore greetings, filler, and small talk.
- Extract concrete facts, not vague statements.

Return a JSON array of memory objects. If nothing to extract, return [].
"""

RECONCILIATION_PROMPT = """You are a memory reconciliation system. Compare new memory candidates against existing memories and determine what to do.

## New Candidates
{candidates}

## Existing Memories
{existing}

## Instructions
For each candidate, decide:
- **add**: New information not in existing memories
- **update**: Updates or adds detail to an existing memory (include the existing memory's ID and what to update)
- **delete**: Contradicts an existing memory (the old one should be removed)
- **discard**: Duplicate or already known

Return a JSON object:
{{
  "add": [{{memory objects to add}}],
  "update": [{{\"id\": \"existing_id\", \"updates\": {{fields to update}}}}],
  "delete": ["id_to_delete"],
  "discard": ["reason for each discarded"]
}}
"""


def format_transcript(turns) -> str:
    """Convert session turns to a readable transcript."""
    lines = []
    for turn in turns:
        role = "User" if turn.role == "user" else "AI"
        lines.append(f"{role}: {turn.content}")
    return "\n".join(lines)


async def pass_1_extract(transcript: str) -> list[dict]:
    """Gemini call: transcript → raw memory candidates."""
    if not transcript.strip():
        return []

    client = _get_client()
    prompt = EXTRACTION_PROMPT.format(transcript=transcript)

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
            )
        )
        return _parse_json_array(response.text)
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")
        return []


async def pass_2_reconcile(candidates: list[dict], existing: list[Memory]) -> dict:
    """Gemini call: candidates + existing → diff {add, update, delete, discard}."""
    if not candidates:
        return {"add": [], "update": [], "delete": [], "discard": []}

    existing_formatted = [
        {"id": str(m.id), "type": m.type.value, "field": m.field,
         "content": m.content, "subtype": m.subtype}
        for m in existing
    ]

    client = _get_client()
    prompt = RECONCILIATION_PROMPT.format(
        candidates=json.dumps(candidates, indent=2),
        existing=json.dumps(existing_formatted, indent=2),
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
            )
        )
        return _parse_diff(response.text)
    except Exception as e:
        logger.error(f"Memory reconciliation failed: {e}")
        return {"add": [], "update": [], "delete": [], "discard": []}


async def apply_diff(diff: dict, user_id: str) -> dict:
    """Apply the reconciliation diff to the database.

    Returns summary of changes made.
    """
    added, updated, deleted = 0, 0, 0

    for mem_data in diff.get("add", []):
        try:
            # Add expires_at for daily_context subtype
            if mem_data.get("subtype") == "daily_context":
                mem_data["expires_at"] = (datetime.utcnow() + timedelta(days=7)).isoformat()
            await memory_repo.create_memory(user_id, mem_data)
            added += 1
        except Exception as e:
            logger.warning(f"Failed to add memory: {e}")

    for update in diff.get("update", []):
        try:
            await memory_repo.update_memory(update["id"], update.get("updates", {}))
            updated += 1
        except Exception as e:
            logger.warning(f"Failed to update memory {update.get('id')}: {e}")

    for mem_id in diff.get("delete", []):
        try:
            await memory_repo.delete_memory(mem_id)
            deleted += 1
        except Exception as e:
            logger.warning(f"Failed to delete memory {mem_id}: {e}")

    return {"added": added, "updated": updated, "deleted": deleted}


async def run_memory_curation(session_id: str) -> dict:
    """Full memory curation pipeline for a session.

    Called as an ARQ background job after session ends.
    """
    session = await Session.get(session_id)
    if session is None:
        logger.error(f"Session {session_id} not found for curation")
        return {"error": "session not found"}

    transcript = format_transcript(session.turns)
    if not transcript.strip():
        return {"skipped": True, "reason": "empty transcript"}

    candidates = await pass_1_extract(transcript)
    if not candidates:
        return {"skipped": True, "reason": "no candidates extracted"}

    existing = await memory_repo.get_all_memories(session.user_id)
    diff = await pass_2_reconcile(candidates, existing)
    result = await apply_diff(diff, session.user_id)

    logger.info(f"Memory curation complete for session {session_id}: {result}")
    return result


def _parse_json_array(raw: str) -> list[dict]:
    """Parse a JSON array from Gemini response."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse extraction response: {text[:200]}")
        return []


def _parse_diff(raw: str) -> dict:
    """Parse a diff JSON object from Gemini response."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else "{}"
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {
                "add": parsed.get("add", []),
                "update": parsed.get("update", []),
                "delete": parsed.get("delete", []),
                "discard": parsed.get("discard", []),
            }
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse reconciliation response: {text[:200]}")

    return {"add": [], "update": [], "delete": [], "discard": []}
