from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    identity_mode: Literal["mock"] = "mock"
    memory_mode: Literal["cache"] = "cache"
    trace_mode: Literal["cache", "databricks"] = "cache"
    database_path: Path = Path(".local/synapse.db")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    agent_provider: Literal["none", "gemini"] = "none"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    databricks_host: str | None = None
    databricks_token: str | None = None
    databricks_warehouse_id: str | None = None
    databricks_catalog: str | None = None
    databricks_schema: str | None = None
    databricks_trace_table: str = "synapse_agent_traces"

    @property
    def resolved_database_path(self) -> Path:
        return ROOT / self.database_path

    @property
    def databricks_trace_table_name(self) -> str:
        if not self.databricks_catalog or not self.databricks_schema:
            return self.databricks_trace_table
        return f"{self.databricks_catalog}.{self.databricks_schema}.{self.databricks_trace_table}"
