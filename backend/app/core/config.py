from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "REKSA API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./reksa.db"
    mqtt_enabled: bool = True
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls: bool = False
    mqtt_ca_cert: str | None = None
    mqtt_client_id: str = "reksa-backend"
    mqtt_ack_enabled: bool = True
    mqtt_dedup_max_messages: int = 5000
    firestore_enabled: bool = False
    google_cloud_project: str | None = None
    firestore_collection: str = "reksa_ingest_events"
    ai_service_url: str = "http://localhost:8100"
    ai_timeout_seconds: float = 2.0
    ai_window_seconds: float = 10.0
    ai_min_samples: int = 2
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    device_offline_timeout: int = 30
    wit_ai_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                import json
                try:
                    parsed = json.loads(trimmed)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [part.strip().strip("'\"") for part in trimmed.split(",") if part.strip().strip("'\"")]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
