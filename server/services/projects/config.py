import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def normalize_service_url(url: str, default_port: int) -> str:
    url = str(url).strip().rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        if ".onrender.com" in url:
            url = f"https://{url}"
        elif ":" not in url:
            url = f"http://{url}:{default_port}"
        else:
            url = f"http://{url}"
    return url


class ProjectSettings(BaseSettings):
    PORT: int = 8002
    MONGODB_URI: str = "mongodb://localhost:27017/nxtbuild"
    AUTH_SERVICE_URL: str = normalize_service_url(os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001"), 8001)

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = ProjectSettings()
