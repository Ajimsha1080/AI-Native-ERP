"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from uuid import UUID
from jose import JWTError, jwt

from packages.database import get_db
from packages.config import get_settings
from packages.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    get_current_user,
)
from packages.security.middleware import token_blacklist_store
from packages.database.models import User, UserRole, UserRoleAssignment
from ..schemas.user import UserLogin, Token, TokenRefresh, UserCreate, UserResponse, UserCreateResponse
from packages.auth.sso import sso_manager

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user.

    Args:
        user_data: User creation data
        db: Database session

    Returns:
        UserCreateResponse: Created user with token

    Raises:
        HTTPException: If email already exists or registration fails
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Hash password
    password_hash = get_password_hash(user_data.password)

    # Create user
    user = User(
        email=user_data.email,
        password_hash=password_hash,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        organization_id=user_data.organization_id,
        is_verified=False,
        status="pending",
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "id": user.id,
        "user": user
    }


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login user.

    Args:
        login_data: Login credentials
        db: Database session

    Returns:
        Token: Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Get user
    result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Generate tokens
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days)
    )

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token.

    Args:
        refresh_data: Refresh token
        db: Database session

    Returns:
        Token: New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        payload = jwt.decode(
            refresh_data.refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: expected refresh token"
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Validate user exists and is active
    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        res = await db.execute(select(User).where(User.id == user_uuid))
        user = res.scalar_one_or_none()
    except (ValueError, TypeError):
        res = await db.execute(select(User).where(User.email == user_id))
        user = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Generate new token pair
    new_access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days)
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        UserResponse: User information
    """
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Logout current user and invalidate token."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        token_blacklist_store.blacklist_token(token)
    return {"message": "Successfully logged out"}


@router.post("/verify")
async def verify_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify user account."""
    current_user.is_verified = True
    current_user.status = "active"
    await db.commit()
    await db.refresh(current_user)
    return {
        "ok": True,
        "message": "User account successfully verified",
        "is_verified": current_user.is_verified
    }


# --- ENTERPRISE SSO & IDENTITY PROVIDER ENDPOINTS ---

@router.get("/sso/providers")
async def get_sso_providers():
    """List enabled enterprise SAML 2.0 / OIDC Identity Providers."""
    return sso_manager.list_providers()


@router.post("/sso/login")
async def sso_login(provider_id: str, redirect_uri: str = "http://localhost:3000/auth/callback"):
    """Generate SAML 2.0 / OIDC Single Sign-On authorization URL."""
    try:
        return sso_manager.generate_sso_auth_url(provider_id, redirect_uri)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sso/callback")
async def sso_callback(provider_id: str, code: str):
    """Process Enterprise SSO Authorization Callback & Return Tokens."""
    user_info = sso_manager.authenticate_sso_callback(provider_id, code)
    access_token = create_access_token(data={"sub": user_info.user_id, "roles": user_info.roles})
    refresh_token = create_refresh_token(data={"sub": user_info.user_id})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_info
    }
