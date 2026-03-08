"""Decision engine — parses the first token from the LLM stream.

The LLM is instructed to output SEARCH or NO_SEARCH as the first token.
This module reads that token and determines the retrieval strategy.
"""

from typing import AsyncIterator, Any

from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _prepend_to_stream(token: str, stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield a token first, then continue with the rest of the stream."""
    yield token
    async for chunk in stream:
        yield chunk


async def get_decision_token(stream: AsyncIterator[str]) -> tuple[str, AsyncIterator[str]]:
    """Read the first token from the LLM stream and classify it.

    Returns:
        tuple: (decision, remaining_stream)
            - decision: "SEARCH" | "NO_SEARCH"
            - remaining_stream: async iterator for the rest of the response

    If the first token is neither SEARCH nor NO_SEARCH, we treat it as
    NO_SEARCH and prepend it back into the stream so it's not lost.
    """
    try:
        first_chunk = await stream.__anext__()
    except StopAsyncIteration:
        logger.warning("Empty LLM stream — defaulting to NO_SEARCH")
        return "NO_SEARCH", _empty_stream()

    token = first_chunk.strip().upper()

    if token == "SEARCH":
        logger.info("Decision: SEARCH")
        return "SEARCH", stream
    elif token == "NO_SEARCH":
        logger.info("Decision: NO_SEARCH")
        return "NO_SEARCH", stream
    else:
        # The LLM didn't follow instructions — the first chunk is actual content.
        # Prepend it back and continue as NO_SEARCH.
        logger.info(f"Decision: fallthrough (token was '{first_chunk.strip()[:50]}')")
        return "NO_SEARCH", _prepend_to_stream(first_chunk, stream)


async def _empty_stream() -> AsyncIterator[str]:
    """An empty async generator."""
    return
    yield  # type: ignore  # makes this a generator
