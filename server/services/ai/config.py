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


class AISettings(BaseSettings):
    PORT: int = 8003
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AUTH_SERVICE_URL: str = normalize_service_url(os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001"), 8001)
    PROJECT_SERVICE_URL: str = normalize_service_url(os.getenv("PROJECT_SERVICE_URL", "http://127.0.0.1:8002"), 8002)

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = AISettings()
