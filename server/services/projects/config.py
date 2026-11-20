import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class ProjectSettings(BaseSettings):
    PORT: int = 8002
    MONGODB_URI: str = "mongodb://localhost:27017/nxtbuild"
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001")

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = ProjectSettings()
