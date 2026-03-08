"""Companion AI Voice Agent — thin I/O wrapper around FastAPI session core.

Architecture:
- STT (Deepgram Nova-3) captures user speech → finalized transcript
- Agent sends transcript to FastAPI /internal/voice-turn via session_bridge
- FastAPI runs decision engine, memory retrieval, filler generation
- Agent speaks filler (if SEARCH) then main response via session.say()
- TTS (Deepgram Aura-2, voice=athena) synthesizes speech
- No LLM runs in the agent process — all intelligence is in FastAPI
"""

import asyncio
import logging
import os
import json

from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    room_io,
)
from livekit.plugins import deepgram, noise_cancellation, silero

from session_bridge import SessionBridge

logger = logging.getLogger("voice-agent")

load_dotenv(".env.local")
load_dotenv(".env")


class CompanionAgent(Agent):
    """Voice agent that delegates intelligence to the FastAPI backend.

    The agent has NO LLM — it captures STT transcripts, sends them to
    the backend, and speaks the response. The backend handles decision
    engine, memory retrieval, prompt building, and response generation.
    """

    def __init__(self, session_id: str, bridge: SessionBridge) -> None:
        super().__init__(
            instructions=(
                "You are a companion AI voice assistant. "
                "Listen to the user and respond naturally."
            ),
        )
        self._session_id = session_id
        self._bridge = bridge
        self._processing = False
        self._turn_counter = 0


server = AgentServer()


def prewarm(proc: JobProcess):
    """Pre-warm the VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="companion-voice")
async def companion_session(ctx: JobContext):
    """Entry point for a voice session.

    The session_id is passed as room metadata by the frontend when it
    creates the LiveKit room (set during token generation).
    """
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Extract session_id from room name (companion-{session_id})
    room_name = ctx.room.name
    session_id = room_name.replace("companion-", "", 1) if room_name.startswith("companion-") else room_name

    # Create session bridge
    backend_url = os.getenv("BACKEND_INTERNAL_URL", "http://localhost:8000")
    bridge = SessionBridge(base_url=backend_url)

    # Create the agent
    agent = CompanionAgent(session_id=session_id, bridge=bridge)

    # Set up the voice session — STT + TTS only, no LLM
    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            language="en",
        ),
        tts=deepgram.TTS(
            model="aura-2-en",
            voice="athena",
        ),
        vad=ctx.proc.userdata["vad"],
        # No LLM — we handle responses manually via session_bridge
    )

    # Start the session
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Register event handler for finalized transcripts
    @session.on("user_input_transcribed")
    async def on_transcript(ev):
        """Handle finalized user transcripts."""
        if not ev.is_final:
            return

        transcript = ev.transcript.strip()
        if not transcript:
            return

        if agent._processing:
            logger.warning(f"Already processing, skipping transcript: {transcript[:50]}")
            return

        agent._processing = True
        try:
            logger.info(f"Processing transcript: {transcript[:100]}")

            # Send to backend for processing
            result = await bridge.process_turn(session_id, transcript)

            # If SEARCH path, speak filler first
            if result.filler_text:
                handle = session.say(result.filler_text, allow_interruptions=True)
                await handle

            # Speak the main response
            if result.response_text:
                agent._turn_counter += 2  # user + agent turns
                handle = session.say(result.response_text, allow_interruptions=True)
                await handle

                # Check if interrupted
                if handle.interrupted:
                    try:
                        await bridge.mark_interrupted(
                            session_id, agent._turn_counter
                        )
                    except Exception as e:
                        logger.warning(f"Failed to mark interruption: {e}")

        except Exception as e:
            logger.error(f"Error processing voice turn: {e}", exc_info=True)
            # Speak a fallback error message
            try:
                session.say(
                    "Sorry, I had trouble processing that. Could you try again?",
                    allow_interruptions=True,
                )
            except Exception:
                pass
        finally:
            agent._processing = False

    # Greet the user
    session.generate_reply(
        instructions="Greet the user warmly. Keep it brief and natural, like 'Hey! How are you doing today?'"
    )

    # Wait for the session to end
    @session.on("close")
    async def on_close():
        """Clean up when the session ends."""
        try:
            await bridge.end_session(session_id)
        except Exception as e:
            logger.warning(f"Failed to end session via bridge: {e}")
        finally:
            await bridge.close()

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
