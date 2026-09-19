from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

Vendor = Literal["none", "gemini", "cerebras", "groq", "github", "openrouter", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    identity_mode: Literal["mock", "ans"] = "mock"
    memory_mode: Literal["cache", "databricks"] = "cache"
    database_path: Path = Path(".local/synapse.db")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Live agents: one vendor per role. "none" = scripted fallback for that role.
    backend_provider: Vendor = "none"
    frontend_provider: Vendor = "none"
    qa_provider: Vendor = "none"

    # Vendor keys. Only the ones you use need to be set.
    gemini_api_key: str | None = None
    gemini_api_key_backend: str | None = None
    gemini_api_key_frontend: str | None = None
    gemini_api_key_qa: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    cerebras_api_key: str | None = None
    cerebras_model: str | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    github_api_key: str | None = None
    github_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None

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
        return self.identity_mode != "mock" or self.memory_mode != "cache"

    @property
    def live_agents_enabled(self) -> bool:
        return any(v != "none" for v in (self.backend_provider, self.frontend_provider,
                                          self.qa_provider))
