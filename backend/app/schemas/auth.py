"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user_id: str
    token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    language: str
    active_trait_ids: list[str]
    onboarding_complete: bool
