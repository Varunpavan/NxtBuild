import os
import re
from datetime import timedelta
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class AuthSettings(BaseSettings):
    PORT: int = 8001
    MONGODB_URI: str = "mongodb://localhost:27017/nxtbuild"
    JWT_SECRET: str = "nxtbuild_default_development_jwt_secret_key_change_in_production"
    JWT_EXPIRES_IN: str = "7d"

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def token_expiration_delta(self) -> timedelta:
        raw = self.JWT_EXPIRES_IN.strip().lower()
        match = re.match(r"^(\d+)([dhm])?$", raw)
        if not match:
            return timedelta(days=7)
        val, unit = match.groups()
        val = int(val)
        if unit == "d":
            return timedelta(days=val)
        elif unit == "h":
            return timedelta(hours=val)
        elif unit == "m":
            return timedelta(minutes=val)
        return timedelta(seconds=val)


settings = AuthSettings()
