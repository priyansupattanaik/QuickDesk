import logging
import secrets

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret_key: str = Field(default="", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    quickdesk_env: str = Field(default="dev", validation_alias="QUICKDESK_ENV")
    nvidia_api_key: str = Field(default="", validation_alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", validation_alias="NVIDIA_BASE_URL")
    nvidia_model: str = Field(default="meta/llama-3.3-70b-instruct", validation_alias="NVIDIA_MODEL")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

