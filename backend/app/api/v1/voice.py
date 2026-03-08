"""Voice API routes — token issuance and internal voice-turn/interrupt endpoints.

Public endpoints (JWT protected):
- POST /api/v1/voice/token — init voice session + return LiveKit token

Internal endpoints (no auth — protected by network isolation):
- POST /internal/voice-turn — process transcript through decision engine
- POST /internal/voice-interrupt — mark a turn as interrupted
"""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.models.session import Session, Turn
from app.schemas.voice import (
    VoiceTokenResponse,
    VoiceTurnRequest,
    VoiceTurnResponse,
    VoiceInterruptRequest,
)
from app.core.session_manager import init_session, end_session
from app.core.prompt_builder import assemble_prompt
from app.core.decision_engine import get_decision_token
from app.core.response_streamer import _stream_llm, get_llm_client
from app.memory.retrieval import retrieve_relevant_memories
from app.voice.token_service import generate_room_token, get_room_name
from app.voice.filler import generate_filler
from app.db.redis_client import get_redis, session_prompt_key, session_history_key
from app.db.repositories import coins_repo
from app.utils.errors import NotFoundError, SessionNotActiveError
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ─── Public endpoints (JWT auth) ────────────────────────────────────────────


@router.post("/token", response_model=VoiceTokenResponse)
async def voice_token(user: User = Depends(get_current_user)):
    """Initialize a voice session and return a LiveKit room token.

    1. Create session (mode=voice) via session_manager
    2. Assemble and cache the prompt in Redis
    3. Generate LiveKit room token
    4. Return session_id, livekit_token, room_name
    """
    user_id = str(user.id)

    # Init session
    session_id = await init_session(user_id, mode="voice")

    # Assemble prompt and cache in Redis
    await assemble_prompt(session_id, user_id)

    # Generate LiveKit token
    livekit_token = generate_room_token(user_id, session_id)
    room_name = get_room_name(session_id)

    logger.info(f"Voice token issued: user={user_id}, session={session_id}, room={room_name}")

    return VoiceTokenResponse(
        session_id=session_id,
        livekit_token=livekit_token,
        room_name=room_name,
    )


# ─── Internal endpoints (no auth — network-isolated) ────────────────────────


@router.post("/internal/voice-turn", response_model=VoiceTurnResponse)
async def internal_voice_turn(request: VoiceTurnRequest):
    """Process a voice transcript through the same pipeline as chat.

    This is called by the LiveKit agent process via session_bridge.

    Flow:
    1. Load cached prompt from Redis
    2. Build messages with history + transcript
    3. Stream from LLM → decision engine → SEARCH or NO_SEARCH
    4. If SEARCH: generate filler + retrieve memories + re-stream with enriched context
    5. If NO_SEARCH: collect full response directly
    6. Persist turns to MongoDB, award coins
    7. Return response_text, filler_text, memory_used
    """
    session_id = request.session_id
    transcript = request.transcript_text
    r = get_redis()

    # Verify session is active
    session = await Session.get(session_id)
    if not session:
        raise NotFoundError("Session", session_id)
    if session.status != "active":
        raise SessionNotActiveError(session_id)

    user_id = session.user_id

    # Load cached prompt
    prompt = await r.get(session_prompt_key(session_id))
    if not prompt:
        prompt = await assemble_prompt(session_id, user_id)

    # Load conversation history from Redis
    raw_history = await r.lrange(session_history_key(session_id), 0, 5)
    history = raw_history if raw_history else []

    # Build messages
    messages = []
    for i, turn_text in enumerate(history):
        role = "user" if i % 2 == 0 else "model"
        messages.append({"role": role, "content": turn_text})
    messages.append({"role": "user", "content": transcript})

    # Stream from LLM
    stream = _stream_llm(prompt, messages)

    # Decision engine
    decision, stream = await get_decision_token(stream)

    memory_used = False
    filler_text = None

    if decision == "SEARCH":
        # Generate filler sentence
        filler_text = await generate_filler(session_id, transcript, user_id)

        # Retrieve relevant memories
        memories = await retrieve_relevant_memories(session_id, transcript, history)
        memory_used = len(memories) > 0

        if memories:
            # Enrich context with retrieved memories
            memory_block = "\n".join(
                f"- {m['content'] if isinstance(m, dict) else m}"
                for m in memories
            )
            enriched_query = (
                f"{transcript}\n\n[Recalled memories relevant to this message:\n{memory_block}]"
            )
            messages[-1] = {"role": "user", "content": enriched_query}

        # Re-stream with enriched context
        stream = _stream_llm(prompt, messages)

    # Collect full response
    full_response = ""
    async for chunk in stream:
        full_response += chunk

    # Persist turns to MongoDB
    turn_count = len(session.turns)

    user_turn = Turn(
        turn_id=turn_count + 1,
        mode="voice",
        role="user",
        content=transcript,
    )

    agent_turn = Turn(
        turn_id=turn_count + 2,
        mode="voice",
        role="agent",
        content=full_response,
        memory_used=memory_used,
        filler_used=filler_text is not None,
    )

    session.turns.append(user_turn)
    session.turns.append(agent_turn)
    await session.save()

    # Update Redis history (keep last 6 turns)
    pipe = r.pipeline()
    pipe.rpush(session_history_key(session_id), transcript)
    pipe.rpush(session_history_key(session_id), full_response)
    pipe.ltrim(session_history_key(session_id), -6, -1)
    await pipe.execute()

    # Award coins
    await coins_repo.award_coins(user_id)

    logger.info(
        f"Voice turn complete: session={session_id}, "
        f"decision={decision}, memory_used={memory_used}, "
        f"filler={'yes' if filler_text else 'no'}, "
        f"response_len={len(full_response)}"
    )

    return VoiceTurnResponse(
        response_text=full_response,
        filler_text=filler_text,
        memory_used=memory_used,
    )


@router.post("/internal/voice-interrupt")
async def internal_voice_interrupt(request: VoiceInterruptRequest):
    """Mark a specific turn as interrupted in MongoDB.

    Called by the LiveKit agent when the user interrupts the agent.
    """
    session = await Session.get(request.session_id)
    if not session:
        raise NotFoundError("Session", request.session_id)

    # Find the turn and mark it as interrupted
    for turn in session.turns:
        if turn.turn_id == request.turn_id:
            turn.interrupted = True
            await session.save()
            logger.info(
                f"Turn {request.turn_id} marked interrupted in session {request.session_id}"
            )
            return {"status": "ok"}

    raise NotFoundError("Turn", str(request.turn_id))
