"""Filler generator — produces persona-shaped filler sentences for voice SEARCH path.

During voice sessions, when the decision engine returns SEARCH, a short natural
filler sentence is spoken while memory retrieval runs in parallel. The filler
must feel like something a real person says while thinking — not a loading indicator.

Rules:
- Exactly one sentence, 8-12 words max
- Never starts answering the question
- No commitment to a specific answer or memory
- Shaped by the user's active persona traits
"""

from google import genai

from app.config import settings
from app.models.user import User
from app.models.trait import Trait
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Default filler when generation fails or no persona is set
DEFAULT_FILLER = "Let me think about that for a moment."

# Lazily initialized Gemini client
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini client for filler generation."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


FILLER_PROMPT_TEMPLATE = """Generate exactly ONE short, natural filler sentence (8-12 words maximum).

This filler sentence is what a person says when they need a moment to think before answering a question.

RULES:
- Do NOT answer or partially answer the question.
- Do NOT reference any specific memories or facts.
- Do NOT say anything like "I remember that..." or "Yes, I know..."
- MUST be exactly ONE sentence.
- MUST be 8-12 words maximum.
- MUST feel natural and human.

{persona_block}
The user just asked: "{query_context}"

Output ONLY the filler sentence, nothing else."""


async def generate_filler(session_id: str, query_context: str, user_id: str | None = None) -> str:
    """Generate a persona-shaped filler sentence for the voice SEARCH path.

    Args:
        session_id: Active session ID (for logging).
        query_context: The user's query text.
        user_id: Optional user ID to load persona traits.

    Returns:
        A single filler sentence string.
    """
    # Build persona block from active traits
    persona_block = ""
    if user_id:
        try:
            user = await User.get(user_id)
            if user and user.active_trait_ids:
                traits = []
                for tid in user.active_trait_ids:
                    trait = await Trait.find_one(Trait.name == tid)
                    if trait:
                        traits.append(trait)
                if traits:
                    modifiers = ", ".join(f"{t.name} ({t.prompt_modifier})" for t in traits)
                    persona_block = (
                        f"Your persona: {modifiers}\n"
                        f"Shape the filler sentence to match this personality tone."
                    )
        except Exception as e:
            logger.warning(f"Failed to load persona traits for filler: {e}")

    if not persona_block:
        persona_block = "Use a warm, neutral tone."

    prompt = FILLER_PROMPT_TEMPLATE.format(
        persona_block=persona_block,
        query_context=query_context,
    )

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.9,
                max_output_tokens=50,
                thinking_config=genai.types.ThinkingConfig(thinking_level="MINIMAL")
            ),
        )

        filler = response.text.strip().strip('"').strip("'")

        # Validate: must be a single sentence, not too long
        if not filler or len(filler.split()) > 20:
            logger.warning(f"Filler too long or empty, using default: '{filler}'")
            return DEFAULT_FILLER

        logger.info(f"Filler generated for session {session_id}: '{filler}'")
        return filler

    except Exception as e:
        logger.error(f"Filler generation failed: {e}")
        return DEFAULT_FILLER
