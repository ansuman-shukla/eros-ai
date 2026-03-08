"""Personality profile document model — Carl Jung-inspired trait system."""

from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field


# Default trait weights seeded at 0.0 for every new user (from PRD §8.2)
DEFAULT_TRAIT_WEIGHTS: dict[str, float] = {
    # Jungian axes
    "introversion": 0.0,
    "extraversion": 0.0,
    "intuition": 0.0,
    "sensing": 0.0,
    "feeling": 0.0,
    "thinking": 0.0,
    "judging": 0.0,
    "perceiving": 0.0,
    # Emotional traits
    "emotional_openness": 0.0,
    "emotional_stability": 0.0,
    "self_doubt": 0.0,
    "optimism": 0.0,
    "anxiety_tendency": 0.0,
    # Cognitive traits
    "curiosity": 0.0,
    "analytical_thinking": 0.0,
    "creativity": 0.0,
    "perfectionism": 0.0,
    "pragmatism": 0.0,
    # Interpersonal traits
    "empathy": 0.0,
    "assertiveness": 0.0,
    "agreeableness": 0.0,
    "trust_tendency": 0.0,
    "conflict_avoidance": 0.0,
    # Behavioral traits
    "discipline": 0.0,
    "impulsivity": 0.0,
    "humor": 0.0,
    "dry_humor": 0.0,
    "vulnerability": 0.0,
    # Motivational traits
    "achievement_drive": 0.0,
    "autonomy_drive": 0.0,
    "connection_drive": 0.0,
    "growth_orientation": 0.0,
}


class PersonalityProfile(Document):
    """Evolving psychological profile of a user.

    Updated incrementally via the trait delta system after every session.
    Never reset — accumulates over the full lifetime of interactions.
    """

    user_id: str
    jungian_type: str | None = None  # e.g. "INFJ"
    type_confidence: float = 0.0
    archetypes: list[dict[str, Any]] = Field(default_factory=list)
    trait_weights: dict[str, float] = Field(
        default_factory=lambda: DEFAULT_TRAIT_WEIGHTS.copy()
    )
    attachment_style: str | None = None
    cognitive_style: str | None = None
    core_values: list[str] = Field(default_factory=list)
    version: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    history: list[dict[str, Any]] = Field(default_factory=list)

    class Settings:
        name = "personality_profiles"
