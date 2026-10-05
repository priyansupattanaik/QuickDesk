import logging
import secrets

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret_key: str = Field(default="", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    quickdesk_env: str = Field(default="dev", validation_alias="QUICKDESK_ENV")
    email_backend: str = Field(default="console", validation_alias="EMAIL_BACKEND")
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="qwen/qwen3.8-27b", validation_alias="GROQ_MODEL")
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_ROOT / ".env", ".env", "../.env"),
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_secret(self) -> "Settings":
        if not self.jwt_secret_key:
            if self.quickdesk_env == "dev":
                self.jwt_secret_key = secrets.token_hex(32)
                logging.warning("JWT_SECRET_KEY is unset; using a generated secret for local development only")
            else:
                raise ValueError("JWT_SECRET_KEY must be set outside QUICKDESK_ENV=dev")
        return self


settings = Settings()

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1",
]
