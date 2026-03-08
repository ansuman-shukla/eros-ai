"""Personality update pipeline — evolves user's psychological profile from sessions.

Two-pass Gemini-powered pipeline:
  Pass 1: Analyze transcript for personality signals (observed, absent, new candidates)
  Pass 2: Generate trait weight deltas and apply them
"""

import json
from datetime import datetime

from google import genai

from app.config import settings
from app.models.session import Session
from app.models.personality import PersonalityProfile
from app.pipelines.memory_curation import format_transcript
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


ANALYSIS_PROMPT = """You are a personality analysis system. Analyze the following conversation for personality indicators.

## Transcript
{transcript}

## Existing Traits (current weights)
{traits}

## Instructions
Identify:
1. **observed_traits**: Traits clearly demonstrated in this conversation (from the existing trait list)
2. **absent_traits**: Traits that were notably absent or contradicted
3. **new_candidates**: New personality traits not in the current profile that emerged

For observed traits, rate signal strength (0.1 = weak signal, 0.5 = strong signal).
For absent traits, rate how strongly the absence was noted.
For new candidates, suggest an initial weight (0.1-0.3).

Return JSON:
{{
  "observed_traits": [{{"trait": "name", "signal_strength": 0.3}}],
  "absent_traits": [{{"trait": "name", "absence_strength": 0.1}}],
  "new_candidates": [{{"trait": "name", "initial_weight": 0.15, "evidence": "..."}}]
}}
"""

DELTA_RULES = """
Delta calculation rules:
- Observed trait: delta = +signal_strength * 0.3 (gradual increase)
- Absent trait: delta = -absence_strength * 0.15 (slower decrease)
- New trait: added at initial_weight if >= 0.1 threshold
- All weights clamped to [0.0, 1.0]
"""


async def pass_1_analyze(transcript: str, profile: PersonalityProfile) -> dict:
    """Analyze transcript for personality signals.

    Returns dict with observed_traits, absent_traits, new_candidates.
    """
    if not transcript.strip():
        return {"observed_traits": [], "absent_traits": [], "new_candidates": []}

    # Format current traits for context
    top_traits = {k: v for k, v in profile.trait_weights.items() if v > 0.0}
    traits_str = json.dumps(top_traits, indent=2) if top_traits else "(no established traits yet)"

    client = _get_client()
    prompt = ANALYSIS_PROMPT.format(
        transcript=transcript,
        traits=traits_str,
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
            )
        )
        return _parse_analysis(response.text)
    except Exception as e:
        logger.error(f"Personality analysis failed: {e}")
        return {"observed_traits": [], "absent_traits": [], "new_candidates": []}


async def pass_2_generate_deltas(signals: dict, profile: PersonalityProfile) -> dict:
    """Generate trait weight deltas from personality signals.

    Pure computation — no LLM call needed.
    """
    deltas = {}

    # Observed traits increase
    for item in signals.get("observed_traits", []):
        trait = item.get("trait", "")
        strength = item.get("signal_strength", 0.1)
        if trait and trait in profile.trait_weights:
            deltas[trait] = strength * 0.3

    # Absent traits decrease
    for item in signals.get("absent_traits", []):
        trait = item.get("trait", "")
        strength = item.get("absence_strength", 0.1)
        if trait and trait in profile.trait_weights:
            deltas[trait] = -(strength * 0.15)

    # New trait candidates
    new_traits = []
    for item in signals.get("new_candidates", []):
        name = item.get("trait", "")
        weight = item.get("initial_weight", 0.15)
        if name and weight >= 0.1:
            new_traits.append({"name": name, "initial_weight": weight})

    return {"deltas": deltas, "new_traits": new_traits}


async def apply_deltas(profile: PersonalityProfile, delta_map: dict) -> dict:
    """Apply trait weight deltas to a personality profile.

    Clamps all values to [0.0, 1.0], increments version, snapshots history.
    Returns summary of changes.
    """
    changes = {"modified": {}, "new": []}

    for trait, delta in delta_map.get("deltas", {}).items():
        old = profile.trait_weights.get(trait, 0.0)
        new_val = max(0.0, min(1.0, old + delta))
        profile.trait_weights[trait] = new_val
        changes["modified"][trait] = {"old": old, "new": new_val, "delta": delta}

    for new_trait in delta_map.get("new_traits", []):
        name = new_trait["name"]
        weight = new_trait["initial_weight"]
        if name not in profile.trait_weights:
            profile.trait_weights[name] = weight
            changes["new"].append({"trait": name, "weight": weight})

    # Snapshot + version increment
    profile.history.append({
        "version": profile.version,
        "timestamp": datetime.utcnow().isoformat(),
        "weights": {k: v for k, v in profile.trait_weights.items() if v > 0.0},
    })
    profile.version += 1
    await profile.save()

    return changes


async def run_personality_update(session_id: str) -> dict:
    """Full personality update pipeline for a session.

    Called as an ARQ background job after session ends.
    """
    session = await Session.get(session_id)
    if session is None:
        logger.error(f"Session {session_id} not found for personality update")
        return {"error": "session not found"}

    profile = await PersonalityProfile.find_one(
        PersonalityProfile.user_id == session.user_id
    )
    if profile is None:
        logger.error(f"No personality profile for user {session.user_id}")
        return {"error": "profile not found"}

    transcript = format_transcript(session.turns)
    if not transcript.strip():
        return {"skipped": True, "reason": "empty transcript"}

    signals = await pass_1_analyze(transcript, profile)
    delta_map = await pass_2_generate_deltas(signals, profile)
    changes = await apply_deltas(profile, delta_map)

    logger.info(f"Personality update for session {session_id}: {len(changes['modified'])} modified, {len(changes['new'])} new")
    return changes


def _parse_analysis(raw: str) -> dict:
    """Parse the analysis JSON from Gemini response."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else "{}"
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {
                "observed_traits": parsed.get("observed_traits", []),
                "absent_traits": parsed.get("absent_traits", []),
                "new_candidates": parsed.get("new_candidates", []),
            }
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse personality analysis: {text[:200]}")

    return {"observed_traits": [], "absent_traits": [], "new_candidates": []}
