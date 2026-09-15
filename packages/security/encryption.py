"""Enterprise Cryptographic Encryption at Rest for ERP Credentials and Secrets."""

import base64
import hashlib
import json
import os
from typing import Any, Optional
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import TypeDecorator, String, Text
from packages.config import get_settings

settings = get_settings()


def get_encryption_suite() -> Fernet:
    """Derive a deterministic 32-byte URL-safe base64 key for AES-256 Fernet authenticated encryption."""
    raw_key = os.getenv("ENCRYPTION_KEY") or getattr(settings, "encryption_key", None) or settings.secret_key
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(fernet_key)


def encrypt_credential(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a sensitive string credential."""
    if plaintext is None:
        return None
    if not plaintext:
        return ""
    suite = get_encryption_suite()
    encrypted_bytes = suite.encrypt(plaintext.encode("utf-8"))
    return "enc:" + encrypted_bytes.decode("utf-8")


def decrypt_credential(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt an encrypted string credential."""
    if ciphertext is None:
        return None
    if not ciphertext.startswith("enc:"):
        return ciphertext  # Return legacy plaintext if not yet encrypted
    
    raw_cipher = ciphertext[4:]
    suite = get_encryption_suite()
    try:
        decrypted_bytes = suite.decrypt(raw_cipher.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception):
        return ciphertext


class EncryptedString(TypeDecorator):
    """SQLIalchemy column type that transparently encrypts strings at rest."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return encrypt_credential(str(value))

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return decrypt_credential(value)


class EncryptedJSON(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts JSON payloads at rest."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        if value is None:
            return None
        serialized = json.dumps(value)
        return encrypt_credential(serialized)

    def process_result_value(self, value: Optional[str], dialect) -> Any:
        if value is None:
            return None
        decrypted = decrypt_credential(value)
        try:
            return json.loads(decrypted) if decrypted else None
        except Exception:
            return decrypted
