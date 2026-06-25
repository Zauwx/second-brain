"""Pydantic v2 schemas for the Auth domain (Phase 3).

Schemas:
  UserCreate     — POST /auth/register request body; validates email (D-12) + password (D-13)
  UserRead       — register / profile response; NEVER includes hashed_password (T-03-01)
  LoginRequest   — POST /auth/login request body
  TokenResponse  — login / refresh response: access_token + refresh_token + token_type
  RefreshRequest — POST /auth/refresh request body (scaffolded for Plan 02)
  LogoutRequest  — POST /auth/logout request body (scaffolded for Plan 02)

Password policy (D-13):
  - Minimum 8 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one digit
  - At least one symbol (non-alphanumeric)
  Violations raise ValueError → FastAPI translates to 422 Unprocessable Entity.
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
    """Request body for POST /auth/register."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        """Enforce D-13 password policy: length + composition."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one symbol")
        return v


class UserRead(BaseModel):
    """Response schema for a registered/authenticated user.

    Never includes hashed_password — omission is enforced at the schema layer (T-03-01).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token pair returned from /auth/login and /auth/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for POST /auth/refresh (Plan 02)."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body for POST /auth/logout (Plan 02)."""

    refresh_token: str
