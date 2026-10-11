from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import SecretStr, field_validator
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

    # Files
    default_quota_mb: int = 1024

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_long(cls, value: SecretStr) -> SecretStr:
        # A short secret could be brute-forced, letting an attacker forge tokens.
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

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
