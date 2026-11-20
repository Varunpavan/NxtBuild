import os
import re
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


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


class GatewaySettings(BaseSettings):
    PORT: int = 5050
    CLIENT_URL: str = "http://localhost:5173"

    AUTH_SERVICE_URL: str = normalize_service_url(os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001"), 8001)
    PROJECT_SERVICE_URL: str = normalize_service_url(os.getenv("PROJECT_SERVICE_URL", "http://127.0.0.1:8002"), 8002)
    AI_SERVICE_URL: str = normalize_service_url(os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8003"), 8003)

    model_config = SettingsConfigDict(
        env_file=(str(ENV_PATH), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        origins = [self.CLIENT_URL.strip().rstrip("/")]
        for fallback in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            if fallback not in origins:
                origins.append(fallback)
        return origins


settings = GatewaySettings()
