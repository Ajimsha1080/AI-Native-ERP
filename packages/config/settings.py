"""
Core configuration settings.

Manages application configuration using Pydantic Settings.
"""

from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Loads settings from environment variables.
    """

    # Application
    app_name: str = "Agentic Business Operating Platform"
    app_version: str = "1.0.0"
    environment: str = "development"

    # Database
    database_url: str = "postgresql://agentic_user:agentic_password@localhost:5432/agentic_platform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Email (optional)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@agenticplatform.com"

    # LLM Provider
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 4000

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-opus-20240229"
    anthropic_temperature: float = 0.7

    google_api_key: str = ""
    google_model: str = "gemini-pro"
    google_temperature: float = 0.7

    # File Upload
    max_upload_size: int = 10485760  # 10MB
    upload_dir: str = "/tmp/uploads"

    # Storage
    storage_type: str = "local"  # local, s3, azure_blob

    # CORS
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000", "http://localhost:80"]

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    # Session
    session_type: str = "redis"  # memory, redis
    session_cookie_secure: bool = True
    session_cookie_http_only: bool = True
    session_cookie_samesite: str = "lax"

    # JWT
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # MFA
    mfa_enabled: bool = False
    mfa_issuer: str = "Agentic Platform"

    # SSO
    sso_enabled: bool = False
    sso_provider: str = "google"  # google, azure-ad, okta

    # RAG
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1-aws"
    pinecone_index_name: str = "agentic-platform"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Vector Store
    vector_store_type: str = "pinecone"  # pinecone, faiss, chroma

    # Workflow Engine
    workflow_engine: str = "celery"  # celery, airflow
    workflow_default_timeout: int = 3600
    workflow_max_retries: int = 3

    # Action Engine
    action_default_timeout: int = 60
    action_max_retries: int = 3
    action_idempotency_enabled: bool = True

    # Approval
    approval_low_risk_threshold: float = 0.0
    approval_medium_risk_threshold: float = 1000.0
    approval_high_risk_threshold: float = 10000.0

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # API Versioning
    api_version: str = "v1"
    api_prefix: str = "/api"

    # Health Check
    health_check_enabled: bool = True
    health_check_interval: int = 30

    # Background Tasks
    batch_size: int = 100
    max_workers: int = 4
    task_timeout: int = 3600

    # Error Handling
    show_errors_in_browser: bool = False
    log_errors_to_file: bool = True
    error_log_file_path: str = "./logs/error.log"

    # Data Retention
    data_retention_days: int = 365
    audit_log_retention_days: int = 365
    session_log_retention_days: int = 90

    # Feature Flags
    feature_flag_agent_automation: bool = True
    feature_flag_approval_workflow: bool = True
    feature_flag_rag_enabled: bool = True
    feature_flag_analytics: bool = True
    feature_flag_billing: bool = True

    # Notifications
    email_notifications_enabled: bool = True
    email_notifications_from: str = "noreply@agenticplatform.com"

    # Webhook
    webhook_enabled: bool = True
    webhook_url: str = ""

    # Notifications (SMS, Email, etc.)
    notification_enabled: bool = True

    # Compliance
    allow_multiple_tenants: bool = True

    # Logging
    log_level: str = "INFO"

    # Sentry
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 1.0

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "agentic-platform"
    otel_exporter_otlp_protocol: str = "grpc"

    # Monitoring
    prometheus_enabled: bool = True
    prometheus_port: int = 9090

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforces critical security constraints in production/staging environments."""
        env = (self.environment or "").strip().lower()
        if env in ("production", "prod", "staging"):
            if not self.secret_key or self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
                raise ValueError(
                    "FATAL SECURITY CONFIGURATION: 'secret_key' must be securely generated and at least 32 characters long in production/staging environments!"
                )
            if self.show_errors_in_browser:
                raise ValueError(
                    "FATAL SECURITY CONFIGURATION: 'show_errors_in_browser' must be False in production/staging environments!"
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance.

    Returns:
        Settings: Settings instance
    """
    return settings
