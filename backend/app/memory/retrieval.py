"""Memory retrieval — semantic matching of cold memories via Gemini SDK.

Fetches all cold memories from Redis, sends them to Gemini Flash Lite
for relevance scoring, and returns the resolved memory entries.
"""

import json
from typing import Any

from google import genai

from app.config import settings
from app.memory.cold_memory import get_all_cold_memories, get_cold_value
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Lazily initialized Gemini client
_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Get or create the Gemini client singleton."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


RETRIEVAL_PROMPT_TEMPLATE = """You are a memory retrieval system. Given a user's message and their stored memories, identify which memories are relevant to the current conversation.

## User's Message
{query}

## Recent Conversation
{history}

## Stored Memories
{memories}

## Instructions
Return ONLY a JSON array of memory IDs that are relevant to the user's message.
If no memories are relevant, return an empty array [].
Only include memories that are directly relevant — don't include tangentially related ones.

Response format: ["id1", "id2", ...]"""


async def retrieve_relevant_memories(
    session_id: str,
    query: str,
    history: list[str] | None = None,
) -> list[dict]:
    """Retrieve cold memories relevant to the user's query.

    1. Fetch all cold memories from Redis
    2. Send to Gemini SDK for relevance scoring
    3. Parse returned IDs
    4. Resolve each ID from Redis

    Args:
        session_id: Active session ID.
        query: The user's current message.
        history: Recent conversation turns (last 2-3).

    Returns:
        List of resolved memory dicts. Empty list on any error.
    """
    all_memories = await get_all_cold_memories(session_id)
    if not all_memories:
        logger.info("No cold memories to search")
        return []

    # Format memories for the prompt
    mem_list = []
    for mem in all_memories:
        if isinstance(mem, str):
            mem = json.loads(mem)
        mem_list.append(f"- ID: {mem['id']} | Content: {mem['content']}")
    memories_block = "\n".join(mem_list)

    history_block = "\n".join(history[-3:]) if history else "(no prior turns)"

    prompt = RETRIEVAL_PROMPT_TEMPLATE.format(
        query=query,
        history=history_block,
        memories=memories_block,
    )

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
            )
        )
        raw_text = response.text.strip()
        mem_ids = _parse_memory_ids(raw_text)
    except Exception as e:
        logger.error(f"Gemini retrieval error: {e}")
        return []

    # Resolve IDs from Redis
    resolved = []
    for mid in mem_ids:
        val = await get_cold_value(session_id, mid)
        if val:
            resolved.append(val)
        else:
            logger.warning(f"Memory ID '{mid}' not found in Redis — skipping")

    logger.info(f"Retrieved {len(resolved)} relevant memories from {len(all_memories)} total")
    return resolved


def _parse_memory_ids(raw: str) -> list[str]:
    """Parse a JSON array of memory IDs from the Gemini response.

    Handles common LLM formatting issues (markdown code blocks, etc).
    """
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse memory IDs from Gemini: {text[:200]}")

    return []
