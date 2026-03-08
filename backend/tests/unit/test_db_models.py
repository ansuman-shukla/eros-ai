"""Phase 0 — Document model tests."""

import pytest
from datetime import datetime

from app.models.user import User
from app.models.memory import Memory, MemoryType
from app.models.session import Session, Turn
from app.models.personality import PersonalityProfile, DEFAULT_TRAIT_WEIGHTS
from app.models.coins import CoinLedger


class TestUserModel:
    """Tests for the User document model."""

    async def test_user_model_creates_with_required_fields(self):
        """User should be created with email, hashed_password, and name."""
        user = User(
            email="test@example.com",
            hashed_password="hashed_abc",
            name="Test User",
        )
        await user.insert()

        fetched = await User.get(user.id)
        assert fetched is not None
        assert fetched.email == "test@example.com"
        assert fetched.hashed_password == "hashed_abc"
        assert fetched.name == "Test User"
        assert fetched.language == "en"
        assert fetched.active_trait_ids == []
        assert fetched.onboarding_complete is False
        assert isinstance(fetched.created_at, datetime)


class TestMemoryModel:
    """Tests for the Memory document model."""

    async def test_memory_model_validates_type_enum(self):
        """Memory type must be 'hot' or 'cold'."""
        hot_mem = Memory(
            user_id="usr_1",
            type=MemoryType.HOT,
            field="name",
            content="Aryan",
        )
        await hot_mem.insert()

        fetched = await Memory.get(hot_mem.id)
        assert fetched.type == MemoryType.HOT

        cold_mem = Memory(
            user_id="usr_1",
            type=MemoryType.COLD,
            content="User met girlfriend on Oct 3rd",
            subtype="relationship_event",
        )
        await cold_mem.insert()

        fetched = await Memory.get(cold_mem.id)
        assert fetched.type == MemoryType.COLD

    async def test_memory_model_invalid_type_raises(self):
        """Invalid memory type should raise a validation error."""
        with pytest.raises(ValueError):
            Memory(
                user_id="usr_1",
                type="invalid",  # type: ignore
                content="test",
            )


class TestSessionModel:
    """Tests for the Session document model."""

    async def test_session_model_turn_appends_correctly(self):
        """Turns should append to the session's turns list."""
        session = Session(user_id="usr_1", mode="chat")
        await session.insert()

        turn1 = Turn(
            turn_id=1, role="user", content="Hello!", mode="chat"
        )
        turn2 = Turn(
            turn_id=2, role="agent", content="Hi there!", mode="chat"
        )

        session.turns.append(turn1)
        session.turns.append(turn2)
        await session.save()

        fetched = await Session.get(session.id)
        assert len(fetched.turns) == 2
        assert fetched.turns[0].role == "user"
        assert fetched.turns[0].content == "Hello!"
        assert fetched.turns[1].role == "agent"
        assert fetched.turns[1].turn_id == 2


class TestPersonalityModel:
    """Tests for the PersonalityProfile document model."""

    async def test_personality_model_defaults_all_traits_to_zero(self):
        """All trait weights should default to 0.0."""
        profile = PersonalityProfile(user_id="usr_1")
        await profile.insert()

        fetched = await PersonalityProfile.get(profile.id)
        assert fetched.trait_weights == DEFAULT_TRAIT_WEIGHTS

        # Verify all weights are 0.0
        for trait, weight in fetched.trait_weights.items():
            assert weight == 0.0, f"Trait '{trait}' should be 0.0, got {weight}"

        # Verify the expected number of traits
        assert len(fetched.trait_weights) == 32

        assert fetched.version == 0
        assert fetched.jungian_type is None
        assert fetched.history == []


class TestCoinLedger:
    """Tests for the CoinLedger document model."""

    async def test_coin_ledger_initializes_correctly(self):
        """CoinLedger should initialize with correct defaults."""
        ledger = CoinLedger(user_id="usr_1")
        await ledger.insert()

        fetched = await CoinLedger.get(ledger.id)
        assert fetched.total_coins == 0
        assert fetched.daily_earned_today == 0
        assert fetched.daily_cap == 100
        assert fetched.diary_pages_owned == 5
        assert fetched.last_reset_date is None
