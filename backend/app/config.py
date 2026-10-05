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
    nvidia_api_key: str = Field(default="", validation_alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", validation_alias="NVIDIA_BASE_URL")
    nvidia_model: str = Field(default="meta/llama-3.2-11b-vision-instruct", validation_alias="NVIDIA_MODEL")
    email_backend: str = Field(default="console", validation_alias="EMAIL_BACKEND")
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_ROOT / ".env", ".env", "../.env"),
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_secret(self) -> "Settings":
        if self.nvidia_api_key:
            self.nvidia_api_key = self.nvidia_api_key.strip().strip('"').strip("'")
        if self.nvidia_model:
            self.nvidia_model = self.nvidia_model.strip().strip('"').strip("'")
        if self.nvidia_base_url:
            self.nvidia_base_url = self.nvidia_base_url.strip().strip('"').strip("'")
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
