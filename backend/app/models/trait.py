"""Trait static document model — persona library entries."""

from beanie import Document


class Trait(Document):
    """A single companion persona trait from the trait library.

    Selected by users in the Agent Settings panel.
    Injected into the system prompt as behavioral modifiers.
    """

    name: str
    category: str  # confidence, warmth, energy, maturity, edge, adult
    prompt_modifier: str  # instruction injected into system prompt
    coin_cost: int = 0
    locked: bool = False

    class Settings:
        name = "traits"
