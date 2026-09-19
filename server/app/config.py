from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    identity_mode: Literal["mock", "ans"] = "mock"
    memory_mode: Literal["cache", "databricks"] = "cache"
    database_path: Path = Path(".local/synapse.db")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Live agents (Hoai)
    agent_provider: Literal["none", "gemini"] = "none"
    gemini_api_key: str | None = None
    gemini_backend_api_key: str | None = None
    gemini_frontend_api_key: str | None = None
    gemini_integration_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # GoDaddy ANS (P4)
    ans_base_url: str = ""
    ans_api_key: str = ""
    ans_api_secret: str = ""

    # Databricks (P3)
    databricks_host: str = ""
    databricks_token: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = ""
    databricks_schema: str = ""

    @property
    def resolved_database_path(self) -> Path:
        return ROOT / self.database_path

    @property
    def live_integrations(self) -> bool:
        return (
            self.identity_mode != "mock"
            or self.memory_mode != "cache"
            or (self.agent_provider == "gemini" and any(self.gemini_agent_api_keys.values()))
        )

    @property
    def gemini_agent_api_keys(self) -> dict[str, str | None]:
        """Use role-specific keys, with the legacy shared key as a local fallback."""
        return {
            "backend": self.gemini_backend_api_key or self.gemini_api_key,
            "frontend": self.gemini_frontend_api_key or self.gemini_api_key,
            "integration": self.gemini_integration_api_key or self.gemini_api_key,
        }
