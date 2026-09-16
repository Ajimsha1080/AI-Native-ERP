"""
Pydantic v2 schemas for authentication endpoints.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """POST /auth/register request body."""
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    organization_name: str   # Creates a new org on first registration

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce minimum password requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class RegisterResponse(BaseModel):
    """POST /auth/register response."""
    user_id: str
    email: str
    organization_id: str
    message: str = "Registration successful. Check your email to verify your account."


class LoginRequest(BaseModel):
    """POST /auth/login request body."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Successful authentication response containing both tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int   # Access token TTL in seconds


class RefreshRequest(BaseModel):
    """POST /auth/refresh request body."""
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    """POST /auth/verify-email request body."""
    token: str


class ForgotPasswordRequest(BaseModel):
    """POST /auth/forgot-password request body."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """POST /auth/reset-password request body."""
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class MessageResponse(BaseModel):
    """Generic success message response."""
    message: str
