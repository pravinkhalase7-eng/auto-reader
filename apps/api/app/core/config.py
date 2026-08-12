from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Teacher"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    secret_key: str = "dev-secret-change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"

    database_url: str = "sqlite+aiosqlite:///./ai_teacher.db"
    cors_origins: str = "http://localhost:3000"

    ai_provider: Literal["local", "gemini", "openai"] = "local"
    ocr_provider: Literal["local", "google", "openai"] = "local"
    tts_provider: Literal["local", "google", "openai", "browser"] = "browser"
    storage_provider: Literal["local", "s3"] = "local"

    openai_api_key: str = ""
    google_ai_api_key: str = ""
    google_cloud_api_key: str = ""

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = ""

    storage_root: str = str(Path(__file__).resolve().parents[2] / "storage")
    max_upload_bytes: int = 15 * 1024 * 1024
    allowed_image_types: str = "image/jpeg,image/png,image/webp,image/heic"

    seed_on_startup: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_image_type_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
