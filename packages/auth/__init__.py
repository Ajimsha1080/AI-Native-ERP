"""Auth package initialiser."""
from packages.auth.password import hash_password, verify_password, needs_rehash
from packages.auth.tokens import (
    create_access_token,
    create_refresh_token,
    create_email_token,
    decode_token,
    TokenPayload,
)
from packages.auth.dependencies import (
    get_current_user,
    require_role,
    require_min_role,
    CurrentUser,
    UserTokenPayload,
)

__all__ = [
    "hash_password",
    "verify_password",
    "needs_rehash",
    "create_access_token",
    "create_refresh_token",
    "create_email_token",
    "decode_token",
    "TokenPayload",
    "get_current_user",
    "require_role",
    "require_min_role",
    "CurrentUser",
    "UserTokenPayload",
]
