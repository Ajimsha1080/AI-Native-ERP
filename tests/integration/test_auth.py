"""
Integration tests for authentication (argon2 hashing, JWT access/refresh, role enforcement).
"""

import pytest
from uuid import uuid4
from packages.auth.password import hash_password, verify_password
from packages.auth.tokens import create_access_token, create_refresh_token, decode_token


def test_argon2_password_hashing():
    password = "SuperSecurePassword123!"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword456", hashed) is False


def test_jwt_access_and_refresh_tokens():
    user_id = uuid4()
    org_id = uuid4()
    role = "manager"

    # Access Token
    access_token = create_access_token(user_id, org_id, role)
    payload = decode_token(access_token)

    assert payload.sub == str(user_id)
    assert payload.org_id == str(org_id)
    assert payload.role == role
    assert payload.token_type == "access"

    # Refresh Token
    refresh_token = create_refresh_token(user_id)
    refresh_payload = decode_token(refresh_token)

    assert refresh_payload.sub == str(user_id)
    assert refresh_payload.token_type == "refresh"
