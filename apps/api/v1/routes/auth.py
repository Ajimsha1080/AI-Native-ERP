"""
Hardened Authentication & Identity Routes for Enterprise Multi-Tenant SaaS.

Implements Phase 1 Stop-Ship Security:
- Server-side password policy enforcement (validate_password_policy)
- Real DB-backed RBAC via OrganizationMember table (no email-substring guessing)
- Refresh token rotation with unique JTI, family_id, and automated reuse detection
- Single-use verification and password reset tokens tracked server-side
- Verified email check prior to production authentication
- Account lockout with backoff after failed consecutive login attempts
- Token blacklist revocation on logout
- Authenticated /auth/me profile endpoint
"""

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.auth.dependencies import CurrentUser, UserTokenPayload, get_current_user
from packages.auth.password import hash_password, needs_rehash, validate_password_policy, verify_password
from packages.auth.tokens import (
    TokenBlacklist,
    create_access_token,
    create_email_token,
    create_refresh_token,
    decode_token,
)
from packages.config.settings import settings
from packages.database.core import AsyncSessionLocal
from packages.database.models.organization import Organization
from packages.database.models.user import (
    OrganizationMember,
    OrganizationMemberRole,
    RefreshToken,
    SingleUseToken,
    User,
    UserStatus,
)
from packages.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserMeResponse,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer = HTTPBearer(auto_error=False)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


async def _send_verification_email(user_id: str, email: str, token: str, user_name: str = "User") -> None:
    """Dispatches verification email via worker dispatcher."""
    from apps.worker.tasks.notifications import send_verification_email_task
    try:
        send_verification_email_task(email=email, verification_token=token, user_name=user_name)
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).error("email.verification_failed", error=str(e), email=email)


async def _send_reset_email(user_id: str, email: str, token: str, user_name: str = "User") -> None:
    """Dispatches password reset email via worker dispatcher."""
    from apps.worker.tasks.notifications import send_password_reset_email_task
    try:
        send_password_reset_email_task(email=email, reset_token=token, user_name=user_name)
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).error("email.reset_failed", error=str(e), email=email)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user and organisation",
)
@router.post(
    "/signup",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register/signup alias for a new user and organisation",
)
async def register(
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: DB,
) -> RegisterResponse:
    """
    Create a new user account and associated organisation with real RBAC.
    """
    # 1. Enforce strict server-side password complexity policy
    policy_valid, policy_err = validate_password_policy(body.password)
    if not policy_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=policy_err,
        )

    # 2. Duplicate email check
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # 3. Create Organization
    base_slug = _slugify(body.organization_name)
    org_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
    org = Organization(
        name=body.organization_name,
        slug=org_slug,
        plan="free",
        status="active",
    )
    db.add(org)
    await db.flush()

    # 4. Create User referencing organization_id
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        full_name=f"{body.first_name} {body.last_name}",
        status=UserStatus.PENDING,
        is_active=True,
        is_verified=False,
        organization_id=org.id,
    )
    db.add(user)
    await db.flush()

    # 5. Create real RBAC owner membership
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=OrganizationMemberRole.OWNER.value,
    )
    db.add(membership)

    # 6. Generate single-use verification token and store hash server-side
    verify_token = create_email_token(user.id, "verify_email", ttl_hours=24)
    token_hash = hashlib.sha256(verify_token.encode("utf-8")).hexdigest()
    su_token = SingleUseToken(
        token_hash=token_hash,
        user_id=user.id,
        purpose="verify_email",
        is_consumed=False,
        expires_at=_utc_now() + timedelta(hours=24),
    )
    db.add(su_token)
    await db.commit()

    background_tasks.add_task(
        _send_verification_email, str(user.id), user.email, verify_token, user.full_name or "User"
    )

    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        organization_id=str(org.id),
        message="Registration successful. Check your email to verify your account.",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive access + refresh tokens",
)
async def login(body: LoginRequest, db: DB) -> TokenResponse:
    """
    Authenticate a user with email and password, enforcing account lockout and real DB RBAC.
    """
    now = _utc_now()
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # 1. Check account lockout / backoff
    if user.is_locked:
        if user.locked_until and user.locked_until > now:
            minutes_left = max(1, int((user.locked_until - now).total_seconds() // 60))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account is temporarily locked due to multiple failed login attempts. Try again in {minutes_left} minutes.",
            )
        else:
            # Lockout period expired: release lock
            user.is_locked = False
            user.login_attempts = 0
            user.locked_until = None

    # 2. Check credentials
    if not user.password_hash or not verify_password(body.password, user.password_hash):
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= 5:
            user.is_locked = True
            user.locked_until = now + timedelta(minutes=15)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # 3. Check verified email outside testing / dev
    if settings.environment not in ("testing", "test", "development"):
        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email address has not been verified. Please verify your email before logging in.",
            )

    # 4. Successful login: reset failed attempts
    user.login_attempts = 0
    user.is_locked = False
    user.locked_until = None
    user.last_login_at = now

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    # 5. Determine RBAC role strictly from database OrganizationMember table
    member_res = await db.execute(
        select(OrganizationMember.role).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == user.organization_id
        )
    )
    db_role = member_res.scalar_one_or_none()
    role = db_role if db_role else "viewer"

    # 6. Issue access token with JTI and email
    access_jti = str(uuid.uuid4())
    access_token = create_access_token(
        user_id=user.id,
        org_id=user.organization_id,
        role=role,
        email=user.email,
        jti=access_jti,
    )

    # 7. Issue refresh token with rotation family_id and persist in DB
    refresh_token_str, refresh_jti, family_id = create_refresh_token(user.id)
    refresh_record = RefreshToken(
        jti=refresh_jti,
        user_id=user.id,
        family_id=family_id,
        is_revoked=False,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token with automated reuse detection",
)
async def refresh_tokens(body: RefreshRequest, db: DB) -> TokenResponse:
    """
    Exchange a valid refresh token for a new token pair.
    Implements true rotation with reuse detection. If a revoked token is reused,
    the entire token family is immediately revoked.
    """
    now = _utc_now()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise credentials_exception

    if payload.token_type != "refresh" or not payload.jti or not payload.sub:
        raise credentials_exception

    user_uuid = UUID(payload.sub)
    token_jti = payload.jti

    # 1. Lookup refresh token in database
    token_res = await db.execute(
        select(RefreshToken).where(RefreshToken.jti == token_jti)
    )
    db_token = token_res.scalar_one_or_none()

    # 2. Check for Token Reuse Detection
    if not db_token or db_token.is_revoked:
        # Compromised token family! Revoke all tokens in family
        if payload.family_id:
            try:
                family_uuid = UUID(payload.family_id)
                await db.execute(
                    update(RefreshToken)
                    .where(RefreshToken.family_id == family_uuid)
                    .values(is_revoked=True, revoked_at=now)
                )
            except Exception:
                pass
        TokenBlacklist.blacklist(token_jti)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected. All sessions in this token family have been revoked for your security.",
        )

    # 3. Check expiration
    if db_token.expires_at < now:
        db_token.is_revoked = True
        db_token.revoked_at = now
        await db.commit()
        raise credentials_exception

    # 4. Invalidate old token (Single-Use Rotation)
    db_token.is_revoked = True
    db_token.revoked_at = now

    # 5. Retrieve User
    user_res = await db.execute(
        select(User).where(User.id == user_uuid, User.is_active == True)
    )
    user = user_res.scalar_one_or_none()
    if not user:
        await db.commit()
        raise credentials_exception

    # 6. Retrieve real DB role
    member_res = await db.execute(
        select(OrganizationMember.role).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == user.organization_id
        )
    )
    role = member_res.scalar_one_or_none() or "viewer"

    # 7. Issue new rotated pair under the same family_id
    new_refresh_str, new_jti, _ = create_refresh_token(user.id, family_id=db_token.family_id)
    new_db_token = RefreshToken(
        jti=new_jti,
        user_id=user.id,
        family_id=db_token.family_id,
        is_revoked=False,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_db_token)

    new_access_token = create_access_token(
        user_id=user.id,
        org_id=user.organization_id,
        role=role,
        email=user.email,
    )
    await db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_str,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke tokens and end session",
)
async def logout(
    request: Request,
    body: Optional[LogoutRequest] = None,
    current_user: Optional[CurrentUser] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: DB = None,
) -> MessageResponse:
    """
    Revoke access token JTI via blacklist and revoke refresh token in database.
    """
    now = _utc_now()
    # Revoke access token JTI
    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.jti:
                TokenBlacklist.blacklist(payload.jti)
            TokenBlacklist.blacklist(credentials.credentials)
        except Exception:
            pass

    # Revoke refresh token if provided
    if body and body.refresh_token:
        try:
            rf_payload = decode_token(body.refresh_token)
            if rf_payload.jti:
                TokenBlacklist.blacklist(rf_payload.jti)
                if db is not None:
                    await db.execute(
                        update(RefreshToken)
                        .where(RefreshToken.jti == rf_payload.jti)
                        .values(is_revoked=True, revoked_at=now)
                    )
                    await db.commit()
        except Exception:
            pass

    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email with single-use token",
)
async def verify_email(body: VerifyEmailRequest, db: DB) -> MessageResponse:
    """Mark the user's email as verified using single-use DB token enforcement."""
    now = _utc_now()
    bad_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired verification token.",
    )
    try:
        payload = decode_token(body.token)
    except JWTError:
        raise bad_token

    if payload.token_type != "verify_email" or not payload.sub:
        raise bad_token

    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()

    # Query SingleUseToken
    su_res = await db.execute(
        select(SingleUseToken).where(
            SingleUseToken.token_hash == token_hash,
            SingleUseToken.purpose == "verify_email",
        )
    )
    su_token = su_res.scalar_one_or_none()

    if not su_token or su_token.is_consumed or su_token.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has already been consumed or is expired.",
        )

    # Consume token
    su_token.is_consumed = True
    su_token.consumed_at = now

    user_res = await db.execute(select(User).where(User.id == UUID(payload.sub)))
    user = user_res.scalar_one_or_none()
    if not user:
        raise bad_token

    user.is_verified = True
    user.email_verified_at = now
    user.status = UserStatus.ACTIVE
    await db.commit()

    return MessageResponse(message="Email verified successfully.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a single-use password reset link",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: DB,
) -> MessageResponse:
    """Send a single-use password reset link without email enumeration."""
    now = _utc_now()
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user:
        reset_token = create_email_token(user.id, "reset_password", ttl_hours=1)
        token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
        su_token = SingleUseToken(
            token_hash=token_hash,
            user_id=user.id,
            purpose="reset_password",
            is_consumed=False,
            expires_at=now + timedelta(hours=1),
        )
        db.add(su_token)
        await db.commit()

        background_tasks.add_task(
            _send_reset_email, str(user.id), user.email, reset_token, user.full_name or "User"
        )

    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using single-use token",
)
async def reset_password(body: ResetPasswordRequest, db: DB) -> MessageResponse:
    """Consume single-use reset token and update password hash."""
    now = _utc_now()
    # 1. Enforce password policy
    policy_valid, policy_err = validate_password_policy(body.new_password)
    if not policy_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=policy_err,
        )

    bad_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token.",
    )
    try:
        payload = decode_token(body.token)
    except JWTError:
        raise bad_token

    if payload.token_type != "reset_password" or not payload.sub:
        raise bad_token

    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()

    su_res = await db.execute(
        select(SingleUseToken).where(
            SingleUseToken.token_hash == token_hash,
            SingleUseToken.purpose == "reset_password",
        )
    )
    su_token = su_res.scalar_one_or_none()

    if not su_token or su_token.is_consumed or su_token.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has already been consumed or is expired.",
        )

    su_token.is_consumed = True
    su_token.consumed_at = now

    user_res = await db.execute(
        select(User).where(User.id == UUID(payload.sub), User.is_active == True)
    )
    user = user_res.scalar_one_or_none()
    if not user:
        raise bad_token

    user.password_hash = hash_password(body.new_password)
    user.updated_at = now

    # Revoke all active refresh tokens for this user on password reset
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .values(is_revoked=True, revoked_at=now)
    )
    await db.commit()

    return MessageResponse(message="Password reset successfully.")


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get profile of authenticated user",
)
async def get_me(
    current_user: CurrentUser,
    db: DB,
) -> UserMeResponse:
    """Return the profile, role, and organization for current authenticated user."""
    user_res = await db.execute(
        select(User).where(User.id == current_user.user_id)
    )
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org_res = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = org_res.scalar_one_or_none()

    # Get DB-backed role
    member_res = await db.execute(
        select(OrganizationMember.role).where(
            OrganizationMember.user_id == current_user.user_id,
            OrganizationMember.organization_id == current_user.org_id
        )
    )
    role = member_res.scalar_one_or_none() or current_user.role or "viewer"

    return UserMeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role,
        organization_id=str(current_user.org_id),
        organization_name=org.name if org else None,
        is_verified=user.is_verified,
    )
