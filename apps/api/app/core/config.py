from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_API_ROOT / ".env", Path(".env"), Path("../../.env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    tts_provider: Literal["local", "google", "openai", "browser", "gemini", "mock"] = "browser"
    storage_provider: Literal["local", "s3"] = "local"

    openai_api_key: str = ""
    google_ai_api_key: str = ""
    google_cloud_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_tts_model: str = "gemini-3.1-flash-tts-preview"
    gemini_tts_voice: str = "Kore"
    elevenlabs_api_key: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"  # Alice — premade classroom voice

    pavi_tts_provider: Literal["gemini", "mock"] = "mock"
    pavi_agent_mode: Literal["adk", "mock"] = "adk"
    voice_call_mode: Literal["mock", "live"] = "mock"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_webhook_base_url: str = ""
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    default_timezone: str = "Asia/Kolkata"
    enable_dev_tools: bool = False
    call_max_retries: int = 2
    call_retry_delays_seconds: str = "300,900"
    pavi_context_messages: int = 16
    reminder_scan_interval_seconds: int = 20

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
    def resolved_gemini_api_key(self) -> str:
        return (self.gemini_api_key or self.google_ai_api_key or "").strip()

    @property
    def resolved_pavi_tts_provider(self) -> str:
        if self.pavi_tts_provider in ("gemini", "mock"):
            return self.pavi_tts_provider
        if self.tts_provider == "gemini":
            return "gemini"
        return "mock"

    @property
    def retry_delay_list(self) -> list[int]:
        delays = []
        for part in self.call_retry_delays_seconds.split(","):
            part = part.strip()
            if part.isdigit():
                delays.append(int(part))
        return delays or [300, 900]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def dev_tools_enabled(self) -> bool:
        return not self.is_production

    @property
    def sync_database_url(self) -> str:
        url = self.database_url
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return url

    @property
    def allowed_image_type_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
