"""Response streamer — orchestrates the chat response generation pipeline.

Flow:
1. Load prompt from Redis
2. Build messages with history + user query
3. Stream from LLM
4. Decision engine → SEARCH or NO_SEARCH
5. If SEARCH → retrieve memories, re-stream with enriched context
6. Stream response chunks to WebSocket
7. Persist turn to MongoDB
8. Award coins
"""

import json
from typing import AsyncIterator

from google import genai

from app.config import settings
from app.db.redis_client import get_redis, session_prompt_key, session_history_key
from app.core.decision_engine import get_decision_token
from app.memory.retrieval import retrieve_relevant_memories
from app.models.session import Session, Turn
from app.db.repositories import coins_repo
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Lazily initialized Gemini client
_client: genai.Client | None = None


def get_llm_client() -> genai.Client:
    """Get or create the Gemini client for chat LLM."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


async def _stream_llm(system_prompt: str, messages: list[dict]) -> AsyncIterator[str]:
    """Stream response from Gemini Pro.

    Yields text chunks as they arrive.
    """
    client = get_llm_client()

    # Build the full content list for Gemini
    contents = []
    for msg in messages:
        contents.append(genai.types.Content(
            role=msg["role"],
            parts=[genai.types.Part(text=msg["content"])],
        ))

    response = client.models.generate_content_stream(
        model="gemini-3.1-flash-lite-preview",
        contents=contents,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
            max_output_tokens=2048,
            thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
        ),
    )

    for chunk in response:
        if chunk.text:
            yield chunk.text


async def stream_chat_response(
    session_id: str,
    query: str,
    websocket,
    user_id: str,
) -> None:
    """Full chat response pipeline.

    Args:
        session_id: Active session ID.
        query: User's message text.
        websocket: WebSocket connection to stream response to.
        user_id: User document ID.
    """
    r = get_redis()

    # Load cached prompt
    prompt = await r.get(session_prompt_key(session_id))
    if not prompt:
        from app.core.prompt_builder import assemble_prompt
        prompt = await assemble_prompt(session_id, user_id)

    # Load conversation history from Redis
    raw_history = await r.lrange(session_history_key(session_id), 0, 5)
    history = raw_history if raw_history else []

    # Build messages
    messages = []
    for i, turn_text in enumerate(history):
        role = "user" if i % 2 == 0 else "model"
        messages.append({"role": role, "content": turn_text})
    messages.append({"role": "user", "content": query})

    # Stream from LLM
    stream = _stream_llm(prompt, messages)

    # Decision engine
    decision, stream = await get_decision_token(stream)

    memory_used = False
    if decision == "SEARCH":
        # Retrieve relevant memories
        memories = await retrieve_relevant_memories(session_id, query, history)
        memory_used = len(memories) > 0

        if memories:
            # Enrich context with retrieved memories
            memory_block = "\n".join(
                f"- {m['content'] if isinstance(m, dict) else m}"
                for m in memories
            )
            enriched_query = (
                f"{query}\n\n[Recalled memories relevant to this message:\n{memory_block}]"
            )
            # Replace last message with enriched version
            messages[-1] = {"role": "user", "content": enriched_query}

        # Re-stream (with enriched or original context)
        stream = _stream_llm(prompt, messages)

    # Stream to WebSocket + accumulate response
    full_response = ""
    async for chunk in stream:
        await websocket.send_text(chunk)
        full_response += chunk

    # Get current turn count
    session = await Session.get(session_id)
    turn_count = len(session.turns) if session else 0

    # Persist user turn
    user_turn = Turn(
        turn_id=turn_count + 1,
        mode="chat",
        role="user",
        content=query,
    )

    # Persist agent turn
    agent_turn = Turn(
        turn_id=turn_count + 2,
        mode="chat",
        role="agent",
        content=full_response,
        memory_used=memory_used,
    )

    if session:
        session.turns.append(user_turn)
        session.turns.append(agent_turn)
        await session.save()

    # Update history in Redis (keep last 6 turns)
    pipe = r.pipeline()
    pipe.rpush(session_history_key(session_id), query)
    pipe.rpush(session_history_key(session_id), full_response)
    pipe.ltrim(session_history_key(session_id), -6, -1)
    await pipe.execute()

    # Award coins
    await coins_repo.award_coins(user_id)

    logger.info(
        f"Chat turn complete: session={session_id}, "
        f"decision={decision}, memory_used={memory_used}, "
        f"response_len={len(full_response)}"
    )
