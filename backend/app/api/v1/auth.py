"""Auth API routes — register, login, and current user."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.db.repositories.user_repo import create_user, get_user_by_email, verify_password
from app.models.coins import CoinLedger
from app.models.personality import PersonalityProfile
from app.utils.jwt import encode_token
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Register a new user.

    Auto-creates:
    - CoinLedger with total_coins=0, diary_pages_owned=5
    - PersonalityProfile with all traits seeded at 0.0
    """
    try:
        user = await create_user(
            email=body.email,
            password=body.password,
            name=body.name,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user_id = str(user.id)

    # Auto-create coin ledger
    ledger = CoinLedger(user_id=user_id)
    await ledger.insert()

    # Auto-create personality profile
    profile = PersonalityProfile(user_id=user_id)
    await profile.insert()

    token = encode_token(user_id)
    return TokenResponse(user_id=user_id, token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate a user and return a JWT."""
    user = await get_user_by_email(body.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = encode_token(str(user.id))
    return TokenResponse(user_id=str(user.id), token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        language=user.language,
        active_trait_ids=user.active_trait_ids,
        onboarding_complete=user.onboarding_complete,
    )
