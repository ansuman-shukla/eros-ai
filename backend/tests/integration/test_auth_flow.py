"""Phase 1 — Auth integration tests."""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.coins import CoinLedger
from app.models.personality import PersonalityProfile, DEFAULT_TRAIT_WEIGHTS


class TestRegister:
    """Integration tests for POST /api/v1/auth/register."""

    async def test_register_creates_user_in_db(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "reg@test.com",
            "password": "Password123!",
            "name": "Reg User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert "user_id" in data

        user = await User.find_one(User.email == "reg@test.com")
        assert user is not None
        assert user.name == "Reg User"

    async def test_register_auto_creates_coin_ledger(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "coins@test.com",
            "password": "Password123!",
            "name": "Coins User",
        })
        assert resp.status_code == 201
        user_id = resp.json()["user_id"]

        ledger = await CoinLedger.find_one(CoinLedger.user_id == user_id)
        assert ledger is not None
        assert ledger.total_coins == 0
        assert ledger.diary_pages_owned == 5

    async def test_register_auto_creates_personality_profile_at_zero(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "pers@test.com",
            "password": "Password123!",
            "name": "Pers User",
        })
        assert resp.status_code == 201
        user_id = resp.json()["user_id"]

        profile = await PersonalityProfile.find_one(PersonalityProfile.user_id == user_id)
        assert profile is not None
        assert profile.version == 0
        for trait, weight in profile.trait_weights.items():
            assert weight == 0.0, f"{trait} should be 0.0"

    async def test_register_duplicate_email_returns_400(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "dup@test.com",
            "password": "Password123!",
            "name": "First",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "email": "dup@test.com",
            "password": "Password456!",
            "name": "Second",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()


class TestLogin:
    """Integration tests for POST /api/v1/auth/login."""

    async def test_login_valid_credentials_returns_jwt(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "login@test.com",
            "password": "Password123!",
            "name": "Login User",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@test.com",
            "password": "Password123!",
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpw@test.com",
            "password": "Correct123!",
            "name": "WP User",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrongpw@test.com",
            "password": "Wrong456!",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "ghost@test.com",
            "password": "Whatever123!",
        })
        assert resp.status_code == 401


class TestGetMe:
    """Integration tests for GET /api/v1/auth/me."""

    async def test_get_me_valid_token_returns_user(self, client: AsyncClient):
        reg = await client.post("/api/v1/auth/register", json={
            "email": "me@test.com",
            "password": "Password123!",
            "name": "Me User",
        })
        token = reg.json()["token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["name"] == "Me User"

    async def test_get_me_no_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_get_me_expired_token_returns_401(self, client: AsyncClient):
        from jose import jwt as jose_jwt
        from datetime import datetime, timedelta
        from app.config import settings

        expired_token = jose_jwt.encode(
            {"sub": "fake_id", "exp": datetime.utcnow() - timedelta(hours=1)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
