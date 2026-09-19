from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    identity_mode: Literal["mock"] = "mock"
    memory_mode: Literal["cache"] = "cache"
    database_path: Path = Path(".local/synapse.db")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def resolved_database_path(self) -> Path:
        return ROOT / self.database_path
