"""Prompt builder — assembles the system prompt for the LLM from 6 components.

Components per PRD §11:
1. Base instructions (hardcoded)
2. Hot memory (user facts from Redis)
3. Active persona traits (from MongoDB via user.active_trait_ids)
4. Personality profile summary
5. Mood inference instructions (hardcoded)
6. Language preference
"""

from app.db.redis_client import get_redis, session_prompt_key
from app.memory.hot_memory import get_hot_from_redis
from app.models.user import User
from app.models.trait import Trait
from app.models.personality import PersonalityProfile
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Hardcoded instruction blocks ────────────────────────────────────────────

BASE_INSTRUCTIONS = """You are a deeply personal AI companion. You remember everything the user tells you.
You are warm, emotionally intelligent, and adaptive. You speak naturally — never robotic.

IMPORTANT: Before every response, output EXACTLY one decision token on its own line:
- Output SEARCH if the user's message references past events, people, places, or anything that might require recalling stored memories.
- Output NO_SEARCH if the message is casual, a greeting, or can be answered from context alone.

After the decision token, write your actual response on the next line.
Never mention the decision token to the user. Never explain it. Just output it silently."""

MOOD_INFERENCE_BLOCK = """## Mood Awareness
Infer the user's emotional state from their message content, punctuation, emoji usage, and conversation context.
Adapt your tone accordingly:
- If they seem sad or stressed, be gentle and validating.
- If they seem excited, match their energy.
- If they seem angry, stay calm and empathetic. Don't be defensive.
- If they seem neutral, maintain a warm baseline.
Never explicitly say \"I can tell you're feeling...\" — just naturally adjust."""


async def assemble_prompt(session_id: str, user_id: str) -> str:
    """Build the full system prompt and cache it in Redis.

    Args:
        session_id: Active session ID.
        user_id: User document ID.

    Returns:
        The assembled system prompt string.
    """
    # [1] Base instructions
    prompt_parts = [BASE_INSTRUCTIONS]

    # [2] Hot memory from Redis
    hot = await get_hot_from_redis(session_id)
    if hot:
        facts = "\n".join(f"- {field}: {value}" for field, value in hot.items())
        prompt_parts.append(f"## User Facts\n{facts}")

    # [3] Active persona traits from MongoDB
    user = await User.get(user_id)
    if user and user.active_trait_ids:
        # First try finding by document IDs
        traits = []
        for tid in user.active_trait_ids:
            trait = await Trait.find_one(Trait.name == tid)
            if trait:
                traits.append(trait)
        if traits:
            modifiers = "\n".join(f"- {t.name}: {t.prompt_modifier}" for t in traits)
            prompt_parts.append(f"## Your Personality Traits\n{modifiers}")

    # [4] Personality profile summary
    profile = await PersonalityProfile.find_one(PersonalityProfile.user_id == user_id)
    if profile:
        summary_parts = []
        if profile.jungian_type:
            summary_parts.append(f"Jungian type: {profile.jungian_type} (confidence: {profile.type_confidence:.1f})")
        if profile.attachment_style:
            summary_parts.append(f"Attachment style: {profile.attachment_style}")
        if profile.cognitive_style:
            summary_parts.append(f"Cognitive style: {profile.cognitive_style}")

        # Top traits (weight > 0.3)
        top_traits = {k: v for k, v in profile.trait_weights.items() if v > 0.3}
        if top_traits:
            sorted_traits = sorted(top_traits.items(), key=lambda x: x[1], reverse=True)
            trait_list = ", ".join(f"{k} ({v:.1f})" for k, v in sorted_traits[:8])
            summary_parts.append(f"Dominant traits: {trait_list}")

        if profile.core_values:
            summary_parts.append(f"Core values: {', '.join(profile.core_values)}")

        if summary_parts:
            prompt_parts.append(f"## User Psychological Profile\n" + "\n".join(f"- {s}" for s in summary_parts))

    # [5] Mood inference block
    prompt_parts.append(MOOD_INFERENCE_BLOCK)

    # [6] Language preference
    language = hot.get("language", "en") if hot else "en"
    if user and user.language:
        language = user.language
    prompt_parts.append(f"## Language\nRespond in {language}.")

    prompt = "\n\n".join(prompt_parts)

    # Cache in Redis
    r = get_redis()
    await r.set(session_prompt_key(session_id), prompt)

    logger.info(f"Prompt assembled for session {session_id} ({len(prompt)} chars)")
    return prompt
