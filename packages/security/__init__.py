"""
Security package.

Provides rate limiting, cryptographic field encryption, AI guardrails, and security middleware.
Authentication and user credential handling are centralized in `packages.auth`.
"""

from .middleware import (
    SecurityMiddleware,
    get_security_middleware,
    verify_token_middleware,
    require_tenant_middleware,
    APIKeyAuth,
    get_api_key_auth,
)

from .rates import (
    RateLimiter,
    get_rate_limiter,
    SecurityRateLimits,
    check_endpoint_rate_limit,
    get_rate_limit_headers,
    cleanup_rate_limit_data
)

from .utils import (
    generate_secure_token,
    generate_uuid,
    generate_api_key,
    generate_verification_code,
    validate_email_address,
    sanitize_input,
    validate_phone_number,
    mask_sensitive_data
)

from .encryption import (
    get_encryption_suite,
    encrypt_credential,
    decrypt_credential,
    EncryptedString,
    EncryptedJSON,
)

from .guardrails import (
    AIGuardrailEngine,
    guardrails
)
AIGuardrails = AIGuardrailEngine

__all__ = [
    # Middleware
    'SecurityMiddleware',
    'get_security_middleware',
    'verify_token_middleware',
    'require_tenant_middleware',
    'APIKeyAuth',
    'get_api_key_auth',
    # Rates
    'RateLimiter',
    'get_rate_limiter',
    'SecurityRateLimits',
    'check_endpoint_rate_limit',
    'get_rate_limit_headers',
    'cleanup_rate_limit_data',
    # Utils
    'generate_secure_token',
    'generate_uuid',
    'generate_api_key',
    'generate_verification_code',
    'validate_email_address',
    'sanitize_input',
    'validate_phone_number',
    'mask_sensitive_data',
    # Encryption
    'get_encryption_suite',
    'encrypt_credential',
    'decrypt_credential',
    'EncryptedString',
    'EncryptedJSON',
    # Guardrails
    'AIGuardrails',
    'guardrails',
]
