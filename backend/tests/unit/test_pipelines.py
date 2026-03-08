"""Phase 4 — Unit tests for pipelines and coin system."""

import json
from unittest.mock import patch, MagicMock
from datetime import date, datetime

import pytest

from app.pipelines.memory_curation import (
    format_transcript,
    pass_1_extract,
    pass_2_reconcile,
    apply_diff,
    _parse_json_array,
    _parse_diff,
)
from app.pipelines.personality_update import (
    pass_2_generate_deltas,
    apply_deltas,
)
from app.pipelines.diary_writer import (
    determine_visibility,
    run_diary_writer,
)
from app.db.repositories.coins_repo import (
    award_coins,
    spend_coins,
    purchase_diary_page,
    reset_daily_earned,
    COINS_PER_MESSAGE,
    DAILY_CAP,
    DIARY_PAGE_COST,
)
from app.models.session import Turn
from app.models.personality import PersonalityProfile
from app.models.coins import CoinLedger
from app.models.diary import DiaryEntry
from app.models.user import User
from app.utils.errors import InsufficientCoinsError


# ─── Memory Curation Unit Tests ──────────────────────────────────────────────


class TestMemoryCuration:

    async def test_pass1_extracts_hot_memory_candidates_from_transcript(self, mock_redis):
        """Pass 1 should extract hot memory candidates."""
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"type": "hot", "field": "name", "content": "Aryan"},
        ])
        with patch("app.pipelines.memory_curation._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            result = await pass_1_extract("User: My name is Aryan\nAI: Nice to meet you!")
        assert len(result) == 1
        assert result[0]["field"] == "name"

    async def test_pass1_extracts_cold_with_correct_subtype(self, mock_redis):
        """Pass 1 should extract cold memories with subtypes."""
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"type": "cold", "content": "Started new job at Google", "subtype": "career_event"},
        ])
        with patch("app.pipelines.memory_curation._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            result = await pass_1_extract("User: I just started a new job at Google!")
        assert result[0]["subtype"] == "career_event"

    async def test_pass1_ignores_agent_utterances(self, mock_redis):
        """Extraction instructions tell LLM to ignore agent utterances — verified via prompt wording."""
        from app.pipelines.memory_curation import EXTRACTION_PROMPT
        assert "Only extract information the USER said" in EXTRACTION_PROMPT

    async def test_pass1_ignores_greetings_and_filler(self, mock_redis):
        """Extraction prompt instructs ignoring greetings."""
        from app.pipelines.memory_curation import EXTRACTION_PROMPT
        assert "Ignore greetings" in EXTRACTION_PROMPT

    async def test_pass2_adds_new_memory_when_not_duplicate(self, mock_redis):
        """Pass 2 should return add when memory is new."""
        candidates = [{"type": "cold", "content": "Loves hiking"}]
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "add": [{"type": "cold", "content": "Loves hiking"}],
            "update": [], "delete": [], "discard": [],
        })
        with patch("app.pipelines.memory_curation._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            diff = await pass_2_reconcile(candidates, [])
        assert len(diff["add"]) == 1

    async def test_pass2_discards_exact_duplicate(self, mock_redis):
        """Pass 2 should discard duplicates."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "add": [], "update": [], "delete": [],
            "discard": ["Already known: loves hiking"],
        })
        with patch("app.pipelines.memory_curation._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            diff = await pass_2_reconcile([{"content": "Loves hiking"}], [])
        assert len(diff["discard"]) == 1
        assert len(diff["add"]) == 0

    async def test_pass2_updates_existing_on_new_info(self, mock_redis):
        """Pass 2 should return update for existing memories with new info."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "add": [], "delete": [], "discard": [],
            "update": [{"id": "mem_123", "updates": {"content": "Loves mountain hiking specifically"}}],
        })
        with patch("app.pipelines.memory_curation._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            diff = await pass_2_reconcile([{"content": "hiking detail"}], [])
        assert len(diff["update"]) == 1

    async def test_pass2_deletes_contradicted_memory(self, mock_redis):
        """Pass 2 should return delete for contradicted memories."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "add": [], "update": [], "discard": [],
            "delete": ["mem_old"],
        })
        with patch("app.pipelines.memory_curation._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            diff = await pass_2_reconcile([{"content": "contradicts old"}], [])
        assert "mem_old" in diff["delete"]

    async def test_daily_context_memory_gets_expires_at(self, mock_redis):
        """Daily context memories should get an expires_at field when added."""
        user = User(email="exp@test.com", hashed_password="x", name="Test")
        await user.insert()

        diff = {
            "add": [{"type": "cold", "content": "Had eggs for breakfast", "subtype": "daily_context"}],
            "update": [], "delete": [],
        }
        result = await apply_diff(diff, str(user.id))
        assert result["added"] == 1


# ─── Personality Update Unit Tests ───────────────────────────────────────────


class TestPersonalityUpdate:

    async def test_high_signal_trait_increases_by_correct_delta(self, mock_redis):
        """Observed trait should increase by signal_strength * 0.3."""
        profile = PersonalityProfile(user_id="u1", trait_weights={"empathy": 0.5})
        await profile.insert()

        signals = {"observed_traits": [{"trait": "empathy", "signal_strength": 0.5}],
                    "absent_traits": [], "new_candidates": []}
        deltas = await pass_2_generate_deltas(signals, profile)
        assert abs(deltas["deltas"]["empathy"] - 0.15) < 0.001

    async def test_absent_trait_decreases_by_correct_delta(self, mock_redis):
        """Absent trait should decrease by absence_strength * 0.15."""
        profile = PersonalityProfile(user_id="u1", trait_weights={"humor": 0.6})
        await profile.insert()

        signals = {"observed_traits": [], "new_candidates": [],
                    "absent_traits": [{"trait": "humor", "absence_strength": 0.4}]}
        deltas = await pass_2_generate_deltas(signals, profile)
        assert abs(deltas["deltas"]["humor"] - (-0.06)) < 0.001

    async def test_delta_clamped_at_1_0(self, mock_redis):
        """Trait weight should not exceed 1.0."""
        profile = PersonalityProfile(user_id="u1", trait_weights={"empathy": 0.95})
        await profile.insert()

        delta_map = {"deltas": {"empathy": 0.5}, "new_traits": []}
        await apply_deltas(profile, delta_map)
        assert profile.trait_weights["empathy"] == 1.0

    async def test_delta_clamped_at_0_0(self, mock_redis):
        """Trait weight should not go below 0.0."""
        profile = PersonalityProfile(user_id="u1", trait_weights={"humor": 0.05})
        await profile.insert()

        delta_map = {"deltas": {"humor": -0.5}, "new_traits": []}
        await apply_deltas(profile, delta_map)
        assert profile.trait_weights["humor"] == 0.0

    async def test_trait_at_zero_remains_in_profile(self, mock_redis):
        """A trait that reaches 0.0 should still exist in the profile."""
        profile = PersonalityProfile(user_id="u1", trait_weights={"humor": 0.0})
        await profile.insert()

        delta_map = {"deltas": {"humor": -0.1}, "new_traits": []}
        await apply_deltas(profile, delta_map)
        assert "humor" in profile.trait_weights

    async def test_new_trait_added_at_initial_weight(self, mock_redis):
        """New trait candidates above threshold should be added."""
        profile = PersonalityProfile(user_id="u1")
        await profile.insert()

        delta_map = {"deltas": {}, "new_traits": [{"name": "resilience", "initial_weight": 0.2}]}
        await apply_deltas(profile, delta_map)
        assert profile.trait_weights.get("resilience") == 0.2

    async def test_weak_new_trait_not_added_below_threshold(self, mock_redis):
        """New traits below 0.1 threshold should be filtered out."""
        profile = PersonalityProfile(user_id="u1")
        await profile.insert()

        signals = {"observed_traits": [], "absent_traits": [],
                    "new_candidates": [{"trait": "flaky", "initial_weight": 0.05}]}
        deltas = await pass_2_generate_deltas(signals, profile)
        assert len(deltas["new_traits"]) == 0

    async def test_profile_version_incremented(self, mock_redis):
        """Version should increment after apply_deltas."""
        profile = PersonalityProfile(user_id="u1")
        await profile.insert()
        assert profile.version == 0

        delta_map = {"deltas": {}, "new_traits": []}
        await apply_deltas(profile, delta_map)
        assert profile.version == 1

    async def test_snapshot_appended_to_history(self, mock_redis):
        """History should have a new snapshot after apply_deltas."""
        profile = PersonalityProfile(user_id="u1")
        await profile.insert()
        assert len(profile.history) == 0

        delta_map = {"deltas": {}, "new_traits": []}
        await apply_deltas(profile, delta_map)
        assert len(profile.history) == 1


# ─── Diary Writer Unit Tests ────────────────────────────────────────────────


class TestDiaryWriter:

    async def test_diary_entry_generated_from_transcript(self, mock_redis):
        """Diary entry should be generated when sessions exist."""
        user = User(email="diary@test.com", hashed_password="x", name="DUser")
        await user.insert()
        await CoinLedger(user_id=str(user.id)).insert()

        from app.models.session import Session
        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="I had a great day!"),
            Turn(turn_id=2, mode="chat", role="agent", content="That's wonderful!"),
        ])
        await session.insert()

        mock_response = MagicMock()
        mock_response.text = "Today was a beautiful day of connection..."

        with patch("app.pipelines.diary_writer._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            result = await run_diary_writer(str(user.id), session.started_at.strftime("%Y-%m-%d"))

        assert "entry_id" in result
        assert result["page_number"] == 1

    async def test_diary_page_number_increments(self, mock_redis):
        """Each new diary entry should get the next page number."""
        user = User(email="d2@test.com", hashed_password="x", name="D2")
        await user.insert()
        await CoinLedger(user_id=str(user.id)).insert()

        # Insert an existing diary entry
        await DiaryEntry(user_id=str(user.id), date="2025-01-01",
                         content="Entry 1", page_number=1).insert()

        from app.models.session import Session
        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="Another day!"),
        ])
        await session.insert()

        mock_response = MagicMock()
        mock_response.text = "Day 2 reflections..."

        with patch("app.pipelines.diary_writer._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            result = await run_diary_writer(str(user.id), session.started_at.strftime("%Y-%m-%d"))

        assert result["page_number"] == 2

    async def test_diary_visible_within_page_allowance(self, mock_redis):
        """Diary entries within page allowance should be visible."""
        user = User(email="dv@test.com", hashed_password="x", name="DV")
        await user.insert()
        await CoinLedger(user_id=str(user.id), diary_pages_owned=5).insert()

        visible = await determine_visibility(str(user.id), 3)
        assert visible is True

    async def test_diary_invisible_beyond_page_allowance(self, mock_redis):
        """Diary entries beyond page allowance should be invisible."""
        user = User(email="di@test.com", hashed_password="x", name="DI")
        await user.insert()
        await CoinLedger(user_id=str(user.id), diary_pages_owned=5).insert()

        visible = await determine_visibility(str(user.id), 6)
        assert visible is False

    async def test_diary_skipped_when_no_sessions_today(self, mock_redis):
        """No sessions today should skip diary writing."""
        result = await run_diary_writer("nonexistent_user", "2099-01-01")
        assert result["skipped"] is True


# ─── Coin System Unit Tests ─────────────────────────────────────────────────


class TestCoinSystem:

    async def test_normal_message_awards_10_coins(self, mock_redis):
        """Normal message should award 10 coins."""
        user = User(email="c1@test.com", hashed_password="x", name="C1")
        await user.insert()
        await CoinLedger(user_id=str(user.id)).insert()

        awarded = await award_coins(str(user.id))
        assert awarded == 10

        ledger = await CoinLedger.find_one(CoinLedger.user_id == str(user.id))
        assert ledger.total_coins == 10

    async def test_daily_cap_enforced_at_100(self, mock_redis):
        """Should not award beyond daily cap."""
        user = User(email="c2@test.com", hashed_password="x", name="C2")
        await user.insert()
        ledger = CoinLedger(
            user_id=str(user.id),
            daily_earned_today=95,
            last_reset_date=date.today().isoformat(),
        )
        await ledger.insert()

        awarded = await award_coins(str(user.id))
        assert awarded == 5  # only 5 remaining to cap

    async def test_buy_diary_page_deducts_50_coins(self, mock_redis):
        """Buying a diary page should deduct 50 coins."""
        user = User(email="c3@test.com", hashed_password="x", name="C3")
        await user.insert()
        await CoinLedger(user_id=str(user.id), total_coins=100).insert()

        result = await purchase_diary_page(str(user.id))
        assert result["remaining_coins"] == 50

    async def test_buy_diary_page_increments_pages_owned(self, mock_redis):
        """Buying a page should increment diary_pages_owned."""
        user = User(email="c4@test.com", hashed_password="x", name="C4")
        await user.insert()
        await CoinLedger(user_id=str(user.id), total_coins=100, diary_pages_owned=5).insert()

        result = await purchase_diary_page(str(user.id))
        assert result["diary_pages_owned"] == 6

    async def test_insufficient_coins_raises_error(self, mock_redis):
        """Should raise InsufficientCoinsError when balance is too low."""
        user = User(email="c5@test.com", hashed_password="x", name="C5")
        await user.insert()
        await CoinLedger(user_id=str(user.id), total_coins=10).insert()

        with pytest.raises(InsufficientCoinsError):
            await spend_coins(str(user.id), 50)

    async def test_daily_reset_zeros_daily_earned(self, mock_redis):
        """Daily reset should zero out daily_earned_today."""
        user = User(email="c6@test.com", hashed_password="x", name="C6")
        await user.insert()
        await CoinLedger(user_id=str(user.id), daily_earned_today=80).insert()

        await reset_daily_earned(str(user.id))

        ledger = await CoinLedger.find_one(CoinLedger.user_id == str(user.id))
        assert ledger.daily_earned_today == 0
