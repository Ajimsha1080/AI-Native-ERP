"""
Password hashing using argon2-cffi.

Argon2id is chosen over bcrypt because it is resistant to both
side-channel attacks (argon2i variant) and GPU/ASIC brute-force
attacks (argon2d variant). OWASP recommends argon2id as the
first-choice algorithm for new applications.

The PasswordHasher default parameters (time_cost=2, memory_cost=65536,
parallelism=2, hash_len=32, salt_len=16) exceed OWASP minimums as of 2024.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# Singleton hasher — creating it once avoids repeated parameter validation
_hasher = PasswordHasher(
    time_cost=2,        # Number of iterations
    memory_cost=65536,  # 64 MiB
    parallelism=2,      # Degree of parallelism
    hash_len=32,        # Output hash length in bytes
    salt_len=16,        # Random salt length in bytes
)


def hash_password(plain: str) -> str:
    """
    Hash a plain-text password using argon2id.

    Args:
        plain: The raw password string from the user.

    Returns:
        A self-describing argon2 hash string (includes algorithm, params, salt).
    """
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against an argon2 hash.

    Args:
        plain: The raw password the user provided on login.
        hashed: The stored hash from the database.

    Returns:
        True if the password matches, False otherwise.
        Never raises — incorrect passwords return False.
    """
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """
    Check if the hash needs to be upgraded (e.g., after a parameter change).

    Call this after a successful login and re-hash if True.

    Args:
        hashed: The stored argon2 hash string.

    Returns:
        True if the hash should be regenerated with current parameters.
    """
    return _hasher.check_needs_rehash(hashed)
