"""Session bridge — HTTP client for calling FastAPI internal endpoints.

The LiveKit agent process is a thin I/O wrapper. All intelligence (memory,
personality, decision engine) lives in the FastAPI backend. This bridge
sends voice transcripts to the backend and receives responses.
"""

import os
import httpx
from dataclasses import dataclass

import logging

logger = logging.getLogger("voice-agent.session_bridge")

BACKEND_URL = os.getenv("BACKEND_INTERNAL_URL", "http://localhost:8000")


@dataclass
class VoiceTurnResult:
    """Result from the backend /internal/voice-turn endpoint."""

    response_text: str
    filler_text: str | None
    memory_used: bool


class SessionBridge:
    """HTTP client for FastAPI internal voice endpoints."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or BACKEND_URL
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def process_turn(
        self, session_id: str, transcript: str
    ) -> VoiceTurnResult:
        """Send a voice transcript to the backend for processing.

        Args:
            session_id: Active session ID.
            transcript: Finalized STT transcript text.

        Returns:
            VoiceTurnResult with response_text, filler_text, memory_used.

        Raises:
            httpx.HTTPStatusError: If the backend returns a non-2xx status.
        """
        client = await self._get_client()
        response = await client.post(
            "/api/v1/voice/internal/voice-turn",
            json={
                "session_id": session_id,
                "transcript_text": transcript,
            },
        )
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"Turn processed: session={session_id}, "
            f"memory_used={data.get('memory_used')}, "
            f"filler={'yes' if data.get('filler_text') else 'no'}"
        )

        return VoiceTurnResult(
            response_text=data["response_text"],
            filler_text=data.get("filler_text"),
            memory_used=data.get("memory_used", False),
        )

    async def mark_interrupted(
        self, session_id: str, turn_id: int
    ) -> None:
        """Mark a turn as interrupted in the backend.

        Args:
            session_id: Session document ID.
            turn_id: The turn number to mark as interrupted.
        """
        client = await self._get_client()
        response = await client.post(
            "/api/v1/voice/internal/voice-interrupt",
            json={
                "session_id": session_id,
                "turn_id": turn_id,
            },
        )
        response.raise_for_status()
        logger.info(f"Turn {turn_id} marked interrupted in session {session_id}")

    async def end_session(self, session_id: str) -> None:
        """End a voice session via the backend.

        Args:
            session_id: Session document ID.
        """
        client = await self._get_client()
        response = await client.post(
            f"/api/v1/session/{session_id}/end",
        )
        response.raise_for_status()
        logger.info(f"Voice session ended: {session_id}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
