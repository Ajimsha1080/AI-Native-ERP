"""
Authentication routes.

Endpoints:
  POST /auth/register        — create user + org, enqueue verification email
  POST /auth/login           — verify credentials, return access+refresh tokens
  POST /auth/refresh         — exchange refresh token for new access+refresh pair
  POST /auth/verify-email    — mark user as verified
  POST /auth/forgot-password — enqueue password reset email
  POST /auth/reset-password  — consume reset token, update password hash

Design:
  - No business logic in this router (credential checking inline here is
    acceptable as it IS authentication logic, not ERP domain logic).
  - `_get_db` is a bare session without tenant context because auth routes
    do not yet know the org_id.
  - Passwords are hashed with argon2id via packages.auth.password.
  - Email delivery is enqueued as a background task.
"""

import re
import uuid
from datetime import timezone, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.auth.password import hash_password, verify_password, needs_rehash
from packages.auth.tokens import (
    create_access_token,
    create_refresh_token,
    create_email_token,
    decode_token,
)
from packages.config.settings import settings
from packages.database.core import AsyncSessionLocal
from packages.database.models.organization import Organization
from packages.database.models.user import User, UserStatus
from packages.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    VerifyEmailRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _get_db():
    """Bare session dependency — no tenant context needed for auth routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DB = Annotated[AsyncSession, Depends(_get_db)]


def _slugify(name: str) -> str:
    """Convert organization name to a URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:100]


async def _send_verification_email(user_id: str, email: str, token: str) -> None:
    """Background task: log verification token (wire to email service in production)."""
    import structlog
    log = structlog.get_logger(__name__)
    log.info("email.verification_queued", user_id=user_id, email=email)


async def _send_reset_email(user_id: str, email: str, token: str) -> None:
    """Background task: log reset token (wire to email service in production)."""
    import structlog
    log = structlog.get_logger(__name__)
    log.info("email.reset_queued", user_id=user_id, email=email)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user and organisation",
)
async def register(
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: DB,
) -> RegisterResponse:
    """
    Create a new user account and associated organisation.

    - Checks for duplicate email (global uniqueness).
    - Creates Organization first, then User referencing the org via tenant_id.
    - Hashes password with argon2id.
    - Enqueues verification email without blocking the response.
    """
    # Duplicate email check
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create the organisation
    base_slug = _slugify(body.organization_name)
    org_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
    org = Organization(
        name=body.organization_name,
        slug=org_slug,
        plan="free",
        status="active",
    )
    db.add(org)
    await db.flush()  # Assign org.id without committing

    # Create the user as the organisation owner
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        full_name=f"{body.first_name} {body.last_name}",
        status=UserStatus.PENDING,
        is_active=True,
        tenant_id=org.id,
    )
    db.add(user)
    await db.flush()
    await db.commit()

    verify_token = create_email_token(user.id, "verify_email", ttl_hours=24)
    background_tasks.add_task(
        _send_verification_email, str(user.id), user.email, verify_token
    )

    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        organization_id=str(org.id),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive access + refresh tokens",
)
async def login(body: LoginRequest, db: DB) -> TokenResponse:
    """
    Authenticate a user with email and password.

    Returns access token (30-min) and refresh token (7-day).
    Transparently re-hashes the password if argon2 parameters have changed.
    """
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user: User | None = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Transparent hash upgrade when argon2 parameters improve
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Assumption: first/only user of an org is the owner.
    # In a multi-user org, load role from UserRoleAssignment table.
    role = "owner"

    access_token = create_access_token(user.id, user.tenant_id, role)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token — get new access + refresh pair",
)
async def refresh_tokens(body: RefreshRequest, db: DB) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise credentials_exception

    if payload.token_type != "refresh":
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == payload.sub, User.is_active == True)
    )
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise credentials_exception

    role = "owner"
    access_token = create_access_token(user.id, user.tenant_id, role)
    new_refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email with the token received on registration",
)
async def verify_email(body: VerifyEmailRequest, db: DB) -> MessageResponse:
    """Mark the user's email as verified and activate the account."""
    bad_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired verification token.",
    )
    try:
        payload = decode_token(body.token)
    except JWTError:
        raise bad_token

    if payload.token_type != "verify_email":
        raise bad_token

    result = await db.execute(select(User).where(User.id == payload.sub))
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise bad_token

    if user.is_verified:
        return MessageResponse(message="Email already verified.")

    user.is_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    user.status = UserStatus.ACTIVE
    await db.commit()

    return MessageResponse(message="Email verified successfully.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset email",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: DB,
) -> MessageResponse:
    """
    Send a password reset link.

    Always returns the same message regardless of whether the email exists
    (prevents email enumeration).
    """
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user: User | None = result.scalar_one_or_none()
    if user:
        reset_token = create_email_token(user.id, "reset_password", ttl_hours=1)
        background_tasks.add_task(
            _send_reset_email, str(user.id), user.email, reset_token
        )

    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using the token from the reset email",
)
async def reset_password(body: ResetPasswordRequest, db: DB) -> MessageResponse:
    """Consume the reset token and update the user's argon2 password hash."""
    bad_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token.",
    )
    try:
        payload = decode_token(body.token)
    except JWTError:
        raise bad_token

    if payload.token_type != "reset_password":
        raise bad_token

    result = await db.execute(
        select(User).where(User.id == payload.sub, User.is_active == True)
    )
    user: User | None = result.scalar_one_or_none()
    if not user:
        raise bad_token

    user.password_hash = hash_password(body.new_password)
    await db.commit()

    return MessageResponse(message="Password reset successfully.")
