from functools import lru_cache
from urllib.parse import quote_plus

from cryptography.fernet import Fernet
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables (filled from .env by Docker)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TrustShare"
    log_level: str = "INFO"

    # PostgreSQL
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # MongoDB
    mongo_user: str
    mongo_password: SecretStr
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_db: str = "trustshare"

    # Redis
    redis_password: SecretStr
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Authentication
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cookie_secure: bool = False  # True in production (HTTPS only); False for http://localhost

    # Multi-factor authentication
    mfa_encryption_key: SecretStr  # Fernet key that encrypts TOTP secrets in the database
    mfa_issuer: str = "TrustShare"  # name shown in Google Authenticator
    mfa_challenge_minutes: int = 5  # time allowed between password and code

    # File encryption (Milestone 2): versioned master keys (KEKs) that wrap each file's own key.
    # Format: "1:<base64 32 bytes>,2:<base64 32 bytes>" – see docs/key-management.md.
    master_keys: SecretStr
    active_master_key_version: int = 1

    # Brute-force protection
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    login_rate_limit_per_minute: int = 10  # per IP address
    register_rate_limit_per_minute: int = 5  # per IP address
    forgot_password_rate_limit_per_minute: int = 5  # per IP address

    # Email (Gmail SMTP). Without SMTP_USER/SMTP_PASSWORD, emails are written to the log instead.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587  # STARTTLS
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    mail_from_name: str = "TrustShare"
    frontend_url: str = "http://localhost:5173"  # where links in emails point to
    password_reset_minutes: int = 15
    email_verification_hours: int = 24
    # False = unverified users can log in (they see a reminder); True = they must verify first.
    require_email_verification: bool = False

    # Google login (OAuth 2.0 / OpenID Connect). Without client id + secret the button is hidden.
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    # Must match an "Authorized redirect URI" in Google Cloud Console exactly.
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret.get_secret_value())

    # Admins may delete an account (and all its files) only after this many days without a login.
    inactive_account_days: int = 30

    # Files
    default_quota_mb: int = 1024
    max_upload_mb: int = 25
    storage_dir: str = "/app/storage"  # inside the container; backend/storage on the laptop

    # Object storage for encrypted files (Milestone 2): RustFS locally, AWS S3 in the cloud.
    # Empty endpoint = real AWS S3; credentials come from .env and are never committed.
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = "trustshare-files"
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_long(cls, value: SecretStr) -> SecretStr:
        # A short secret could be brute-forced, letting an attacker forge tokens.
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @field_validator("mfa_encryption_key")
    @classmethod
    def mfa_key_must_be_valid(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value())
        except ValueError as exc:
            raise ValueError("MFA_ENCRYPTION_KEY must be a valid Fernet key") from exc
        return value

    @model_validator(mode="after")
    def master_keys_must_be_valid(self) -> "Settings":
        # Imported here to avoid a circular import (the keyring reads these settings).
        from app.crypto.keyring import parse_master_keys

        keys = parse_master_keys(self.master_keys.get_secret_value())  # raises on bad format
        if self.active_master_key_version not in keys:
            raise ValueError(
                f"ACTIVE_MASTER_KEY_VERSION={self.active_master_key_version} is not in MASTER_KEYS"
            )
        return self

    @property
    def postgres_url(self) -> str:
        password = quote_plus(self.postgres_password.get_secret_value())
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def mongo_url(self) -> str:
        password = quote_plus(self.mongo_password.get_secret_value())
        return (
            f"mongodb://{self.mongo_user}:{password}"
            f"@{self.mongo_host}:{self.mongo_port}/?authSource=admin"
        )

    @property
    def redis_url(self) -> str:
        password = quote_plus(self.redis_password.get_secret_value())
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
