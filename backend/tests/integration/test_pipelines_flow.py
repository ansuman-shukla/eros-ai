"""Phase 4 — Pipeline and coin system integration tests."""

import json
from datetime import date
from unittest.mock import patch, MagicMock

from httpx import AsyncClient

from app.models.user import User
from app.models.memory import Memory, MemoryType
from app.models.session import Session, Turn
from app.models.coins import CoinLedger
from app.models.diary import DiaryEntry
from app.models.personality import PersonalityProfile


class TestMemoryCurationIntegration:

    async def test_curation_job_adds_new_memories_to_mongo(self, mock_redis):
        """Running curation should add new memories to MongoDB."""
        user = User(email="mc1@test.com", hashed_password="x", name="MC1")
        await user.insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="My name is Aryan and I live in Mumbai"),
            Turn(turn_id=2, mode="chat", role="agent", content="Nice to meet you, Aryan!"),
        ])
        await session.insert()

        # Mock pass_1 to return candidates
        candidates = [
            {"type": "hot", "field": "name", "content": "Aryan"},
            {"type": "hot", "field": "city", "content": "Mumbai"},
        ]
        # Mock pass_2 to return add diff
        diff = {"add": candidates, "update": [], "delete": [], "discard": []}

        with patch("app.pipelines.memory_curation.pass_1_extract", return_value=candidates), \
             patch("app.pipelines.memory_curation.pass_2_reconcile", return_value=diff):
            from app.pipelines.memory_curation import run_memory_curation
            result = await run_memory_curation(str(session.id))

        assert result["added"] == 2
        mems = await Memory.find(Memory.user_id == str(user.id)).to_list()
        assert len(mems) == 2

    async def test_curation_job_updates_existing_memory(self, mock_redis):
        """Curation should update existing memories."""
        user = User(email="mc2@test.com", hashed_password="x", name="MC2")
        await user.insert()

        mem = await Memory(user_id=str(user.id), type=MemoryType.HOT,
                           field="city", content="Delhi").insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="I moved to Mumbai"),
        ])
        await session.insert()

        candidates = [{"type": "hot", "field": "city", "content": "Mumbai"}]
        diff = {
            "add": [], "delete": [], "discard": [],
            "update": [{"id": str(mem.id), "updates": {"content": "Mumbai"}}],
        }

        with patch("app.pipelines.memory_curation.pass_1_extract", return_value=candidates), \
             patch("app.pipelines.memory_curation.pass_2_reconcile", return_value=diff):
            from app.pipelines.memory_curation import run_memory_curation
            result = await run_memory_curation(str(session.id))

        assert result["updated"] == 1
        updated = await Memory.get(str(mem.id))
        assert updated.content == "Mumbai"

    async def test_curation_job_deletes_contradicted_memory(self, mock_redis):
        """Curation should delete contradicted memories."""
        user = User(email="mc3@test.com", hashed_password="x", name="MC3")
        await user.insert()

        mem = await Memory(user_id=str(user.id), type=MemoryType.HOT,
                           field="status", content="Single").insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="I got married!"),
        ])
        await session.insert()

        candidates = [{"type": "hot", "field": "status", "content": "Married"}]
        diff = {"add": [], "update": [], "discard": [],
                "delete": [str(mem.id)]}

        with patch("app.pipelines.memory_curation.pass_1_extract", return_value=candidates), \
             patch("app.pipelines.memory_curation.pass_2_reconcile", return_value=diff):
            from app.pipelines.memory_curation import run_memory_curation
            result = await run_memory_curation(str(session.id))

        assert result["deleted"] == 1
        deleted = await Memory.get(str(mem.id))
        assert deleted is None


class TestPersonalityUpdateIntegration:

    async def test_personality_job_updates_trait_weights_in_mongo(self, mock_redis):
        """Pipeline should modify trait weights in MongoDB."""
        user = User(email="pu1@test.com", hashed_password="x", name="PU1")
        await user.insert()
        profile = PersonalityProfile(user_id=str(user.id), trait_weights={"empathy": 0.5})
        await profile.insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="I feel really bad for my friend"),
        ])
        await session.insert()

        signals = {"observed_traits": [{"trait": "empathy", "signal_strength": 0.5}],
                    "absent_traits": [], "new_candidates": []}

        with patch("app.pipelines.personality_update.pass_1_analyze", return_value=signals):
            from app.pipelines.personality_update import run_personality_update
            result = await run_personality_update(str(session.id))

        updated = await PersonalityProfile.find_one(PersonalityProfile.user_id == str(user.id))
        assert updated.trait_weights["empathy"] > 0.5

    async def test_personality_job_adds_new_emergent_trait(self, mock_redis):
        """Pipeline should add new traits that emerge from conversation."""
        user = User(email="pu2@test.com", hashed_password="x", name="PU2")
        await user.insert()
        profile = PersonalityProfile(user_id=str(user.id))
        await profile.insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="I'm really passionate about art"),
        ])
        await session.insert()

        signals = {"observed_traits": [], "absent_traits": [],
                    "new_candidates": [{"trait": "artistic", "initial_weight": 0.2, "evidence": "passionate about art"}]}

        with patch("app.pipelines.personality_update.pass_1_analyze", return_value=signals):
            from app.pipelines.personality_update import run_personality_update
            await run_personality_update(str(session.id))

        updated = await PersonalityProfile.find_one(PersonalityProfile.user_id == str(user.id))
        assert "artistic" in updated.trait_weights

    async def test_personality_job_snapshots_history_entry(self, mock_redis):
        """Pipeline should add a snapshot to history."""
        user = User(email="pu3@test.com", hashed_password="x", name="PU3")
        await user.insert()
        profile = PersonalityProfile(user_id=str(user.id))
        await profile.insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="test"),
        ])
        await session.insert()

        signals = {"observed_traits": [], "absent_traits": [], "new_candidates": []}

        with patch("app.pipelines.personality_update.pass_1_analyze", return_value=signals):
            from app.pipelines.personality_update import run_personality_update
            await run_personality_update(str(session.id))

        updated = await PersonalityProfile.find_one(PersonalityProfile.user_id == str(user.id))
        assert len(updated.history) == 1
        assert updated.version == 1

    async def test_two_sessions_cumulative_not_overwritten(self, mock_redis):
        """Running pipeline twice should accumulate, not overwrite."""
        user = User(email="pu4@test.com", hashed_password="x", name="PU4")
        await user.insert()
        profile = PersonalityProfile(user_id=str(user.id), trait_weights={"empathy": 0.5})
        await profile.insert()

        for i in range(2):
            session = Session(user_id=str(user.id), mode="chat", turns=[
                Turn(turn_id=1, mode="chat", role="user", content=f"Check {i}"),
            ])
            await session.insert()

            signals = {"observed_traits": [{"trait": "empathy", "signal_strength": 0.3}],
                        "absent_traits": [], "new_candidates": []}

            with patch("app.pipelines.personality_update.pass_1_analyze", return_value=signals):
                from app.pipelines.personality_update import run_personality_update
                await run_personality_update(str(session.id))

        updated = await PersonalityProfile.find_one(PersonalityProfile.user_id == str(user.id))
        assert updated.version == 2
        assert len(updated.history) == 2
        assert updated.trait_weights["empathy"] > 0.5


class TestDiaryIntegration:

    async def test_diary_entry_written_for_active_user(self, mock_redis):
        """Diary should be written when user had sessions."""
        user = User(email="di1@test.com", hashed_password="x", name="DI1")
        await user.insert()
        await CoinLedger(user_id=str(user.id)).insert()

        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="Had a great day!"),
        ])
        await session.insert()

        mock_response = MagicMock()
        mock_response.text = "Today I reflected on our wonderful conversation..."

        with patch("app.pipelines.diary_writer._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            from app.pipelines.diary_writer import run_diary_writer
            result = await run_diary_writer(
                str(user.id), session.started_at.strftime("%Y-%m-%d")
            )

        assert "entry_id" in result
        entry = await DiaryEntry.get(result["entry_id"])
        assert "wonderful" in entry.content

    async def test_diary_visibility_matches_pages_owned(self, mock_redis):
        """Entry should be visible if page_number <= pages_owned."""
        user = User(email="di2@test.com", hashed_password="x", name="DI2")
        await user.insert()
        await CoinLedger(user_id=str(user.id), diary_pages_owned=1).insert()

        # First entry should be visible (page 1, owned 1)
        session = Session(user_id=str(user.id), mode="chat", turns=[
            Turn(turn_id=1, mode="chat", role="user", content="Day 1"),
        ])
        await session.insert()

        mock_response = MagicMock()
        mock_response.text = "Day 1 entry"

        with patch("app.pipelines.diary_writer._get_client") as mc:
            mc.return_value.models.generate_content.return_value = mock_response
            from app.pipelines.diary_writer import run_diary_writer
            r1 = await run_diary_writer(str(user.id), session.started_at.strftime("%Y-%m-%d"))

        assert r1["visible"] is True

    async def test_buying_page_reveals_previously_locked_entry(self, client: AsyncClient, seeded_user):
        """Purchasing a page should reveal a locked diary entry."""
        uid = seeded_user["user_id"]

        # Add a locked diary entry at page 6 (user owns 5 by default)
        await DiaryEntry(user_id=uid, date="2025-06-15", content="Locked entry",
                         page_number=6, visible_to_user=False).insert()

        # Give user enough coins
        ledger = await CoinLedger.find_one(CoinLedger.user_id == uid)
        ledger.total_coins = 100
        await ledger.save()

        # Buy page
        resp = await client.post(
            "/api/v1/coins/buy-diary-page",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["diary_pages_owned"] == 6

        # Verify entry is now visible
        entry = await DiaryEntry.find_one(DiaryEntry.user_id == uid, DiaryEntry.page_number == 6)
        assert entry.visible_to_user is True


class TestCoinEndpoints:

    async def test_coin_balance_endpoint_returns_correct_total(self, client: AsyncClient, seeded_user):
        """GET /coins/balance should return correct balance."""
        resp = await client.get(
            "/api/v1/coins/balance",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_coins" in data
        assert "daily_cap" in data

    async def test_buy_diary_page_endpoint_spends_coins_and_increments(self, client: AsyncClient, seeded_user):
        """POST /coins/buy-diary-page should deduct coins and increment pages."""
        uid = seeded_user["user_id"]
        ledger = await CoinLedger.find_one(CoinLedger.user_id == uid)
        ledger.total_coins = 200
        await ledger.save()

        resp = await client.post(
            "/api/v1/coins/buy-diary-page",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remaining_coins"] == 150
        assert data["diary_pages_owned"] == 6
