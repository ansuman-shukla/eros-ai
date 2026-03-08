"""Phase 6.1 — Dashboard endpoint integration tests.

Tests cover all 5 dashboard/persona endpoints:
- GET /api/v1/dashboard/personality
- GET /api/v1/dashboard/activity
- GET /api/v1/dashboard/diary
- GET /api/v1/dashboard/traits
- PATCH /api/v1/persona/active
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.session import Session, Turn
from app.models.personality import PersonalityProfile
from app.models.diary import DiaryEntry
from app.models.trait import Trait
from app.models.coins import CoinLedger


class TestPersonalityEndpoint:

    async def test_personality_endpoint_returns_current_profile_for_user(
        self, client: AsyncClient, seeded_user
    ):
        """GET /dashboard/personality should return the full personality profile."""
        user_id = seeded_user["user_id"]

        # Update profile with data
        profile = await PersonalityProfile.find_one(
            PersonalityProfile.user_id == user_id
        )
        profile.jungian_type = "INFJ"
        profile.type_confidence = 0.85
        profile.attachment_style = "secure"
        profile.cognitive_style = "intuitive"
        profile.core_values = ["empathy", "creativity"]
        profile.trait_weights["empathy"] = 0.9
        profile.trait_weights["curiosity"] = 0.7
        await profile.save()

        resp = await client.get(
            "/api/v1/dashboard/personality",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["jungian_type"] == "INFJ"
        assert data["type_confidence"] == 0.85
        assert data["attachment_style"] == "secure"
        assert data["cognitive_style"] == "intuitive"
        assert "empathy" in data["core_values"]
        assert data["trait_weights"]["empathy"] == 0.9

    async def test_personality_endpoint_requires_auth(self, client: AsyncClient):
        """Personality endpoint should reject unauthenticated requests."""
        resp = await client.get("/api/v1/dashboard/personality")
        assert resp.status_code in (401, 403, 422)


class TestActivityEndpoint:

    async def test_activity_endpoint_returns_per_day_counts(
        self, client: AsyncClient, seeded_user
    ):
        """GET /dashboard/activity should return per-day session/turn counts."""
        user_id = seeded_user["user_id"]

        # Create a session with turns
        session = Session(
            user_id=user_id,
            mode="chat",
            status="ended",
            started_at=datetime.utcnow(),
            turns=[
                Turn(turn_id=1, mode="chat", role="user", content="Hi"),
                Turn(turn_id=2, mode="chat", role="agent", content="Hello!"),
                Turn(turn_id=3, mode="voice", role="user", content="Hey"),
                Turn(turn_id=4, mode="voice", role="agent", content="Hi there!"),
            ],
        )
        await session.insert()

        resp = await client.get(
            "/api/v1/dashboard/activity",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 1
        assert data["total_turns"] == 4
        assert len(data["days"]) >= 1

        # Check breakdown of today's activity
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_data = next((d for d in data["days"] if d["date"] == today), None)
        assert today_data is not None
        assert today_data["session_count"] == 1
        assert today_data["chat_turns"] == 2
        assert today_data["voice_turns"] == 2

    async def test_activity_excludes_old_sessions(
        self, client: AsyncClient, seeded_user
    ):
        """Sessions older than the specified days should be excluded."""
        user_id = seeded_user["user_id"]

        # Create a session 40 days ago
        old_session = Session(
            user_id=user_id,
            mode="chat",
            status="ended",
            started_at=datetime.utcnow() - timedelta(days=40),
            turns=[Turn(turn_id=1, mode="chat", role="user", content="old msg")],
        )
        await old_session.insert()

        resp = await client.get(
            "/api/v1/dashboard/activity?days=30",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["total_turns"] == 0


class TestDiaryEndpoint:

    async def test_diary_endpoint_returns_only_visible_entries(
        self, client: AsyncClient, seeded_user
    ):
        """GET /dashboard/diary should return only visible entries."""
        user_id = seeded_user["user_id"]

        # Create visible and hidden entries
        await DiaryEntry(
            user_id=user_id, date="2024-11-21", content="A great day!",
            visible_to_user=True, page_number=1,
        ).insert()
        await DiaryEntry(
            user_id=user_id, date="2024-11-22", content="Secret entry",
            visible_to_user=False, page_number=6,
        ).insert()

        resp = await client.get(
            "/api/v1/dashboard/diary",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["content"] == "A great day!"

    async def test_diary_endpoint_excludes_entries_beyond_page_allowance(
        self, client: AsyncClient, seeded_user
    ):
        """Entries on pages beyond the user's owned pages should not be visible."""
        user_id = seeded_user["user_id"]

        # Default pages_owned is 5
        # Entry on page 6 with visible_to_user=False should be excluded
        await DiaryEntry(
            user_id=user_id, date="2024-11-20", content="Page 1 entry",
            visible_to_user=True, page_number=1,
        ).insert()
        await DiaryEntry(
            user_id=user_id, date="2024-11-30", content="Page 6 locked",
            visible_to_user=False, page_number=6,
        ).insert()

        resp = await client.get(
            "/api/v1/dashboard/diary",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        data = resp.json()
        # Only page 1 entry visible
        assert data["total"] == 1
        contents = [e["content"] for e in data["entries"]]
        assert "Page 6 locked" not in contents
        assert data["pages_owned"] == 5

    async def test_diary_pagination_works(
        self, client: AsyncClient, seeded_user
    ):
        """Diary should return paginated results."""
        user_id = seeded_user["user_id"]

        for i in range(15):
            await DiaryEntry(
                user_id=user_id, date=f"2024-11-{i+1:02d}",
                content=f"Entry {i+1}", visible_to_user=True, page_number=1,
            ).insert()

        resp = await client.get(
            "/api/v1/dashboard/diary?page=1&page_size=5",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        data = resp.json()
        assert data["total"] == 15
        assert len(data["entries"]) == 5
        assert data["page"] == 1
        assert data["page_size"] == 5


class TestTraitsEndpoint:

    async def test_traits_endpoint_returns_full_library_with_active_flagged(
        self, client: AsyncClient, seeded_user
    ):
        """GET /dashboard/traits should return all traits with is_active flag."""
        # Create traits
        await Trait(
            name="Bold", category="confidence",
            prompt_modifier="You are bold.", coin_cost=0,
        ).insert()
        await Trait(
            name="Gentle", category="warmth",
            prompt_modifier="You are gentle.", coin_cost=10,
        ).insert()
        await Trait(
            name="Witty", category="humor",
            prompt_modifier="You are witty.", coin_cost=20, locked=True,
        ).insert()

        # Set Bold as active for the user
        from app.models.user import User
        user = await User.get(seeded_user["user_id"])
        user.active_trait_ids = ["Bold"]
        await user.save()

        resp = await client.get(
            "/api/v1/dashboard/traits",
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["traits"]) == 3
        assert data["active_trait_ids"] == ["Bold"]

        # Check is_active flags
        bold = next(t for t in data["traits"] if t["name"] == "Bold")
        gentle = next(t for t in data["traits"] if t["name"] == "Gentle")
        witty = next(t for t in data["traits"] if t["name"] == "Witty")
        assert bold["is_active"] is True
        assert gentle["is_active"] is False
        assert witty["locked"] is True


class TestUpdateActiveTraits:

    async def test_update_active_traits_persists_to_mongo(
        self, client: AsyncClient, seeded_user
    ):
        """PATCH /persona/active should persist new active trait IDs."""
        resp = await client.patch(
            "/api/v1/persona/active",
            json={"active_trait_ids": ["Bold", "Gentle"]},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_trait_ids"] == ["Bold", "Gentle"]

        # Verify in MongoDB
        from app.models.user import User
        user = await User.get(seeded_user["user_id"])
        assert user.active_trait_ids == ["Bold", "Gentle"]

    async def test_update_active_traits_replaces_previous(
        self, client: AsyncClient, seeded_user
    ):
        """Updating traits should replace, not append."""
        # First update
        await client.patch(
            "/api/v1/persona/active",
            json={"active_trait_ids": ["Bold", "Gentle"]},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        # Second update — should replace
        resp = await client.patch(
            "/api/v1/persona/active",
            json={"active_trait_ids": ["Witty"]},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        data = resp.json()
        assert data["active_trait_ids"] == ["Witty"]

        from app.models.user import User
        user = await User.get(seeded_user["user_id"])
        assert user.active_trait_ids == ["Witty"]

    async def test_update_active_traits_to_empty_list(
        self, client: AsyncClient, seeded_user
    ):
        """Setting active traits to an empty list should clear them."""
        resp = await client.patch(
            "/api/v1/persona/active",
            json={"active_trait_ids": []},
            headers={"Authorization": f"Bearer {seeded_user['token']}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["active_trait_ids"] == []
