from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
Vendor = Literal["none", "gemini", "cerebras", "groq", "github", "openrouter", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    identity_mode: Literal["mock", "ans"] = "mock"
    memory_mode: Literal["cache", "databricks"] = "cache"
    trace_mode: Literal["cache", "databricks"] = "cache"
    database_path: Path = Path(".local/synapse.db")
    # Shared secret for destructive or billable endpoints: /api/demo/run,
    # /api/reset and the live-agent routes. Unset means those refuse to run.
    demo_token: str | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # One independent provider per role. "none" keeps that live role unconfigured.
    backend_provider: Vendor = "none"
    frontend_provider: Vendor = "none"
    qa_provider: Vendor = "none"

    # Gemini supports a shared fallback key plus a dedicated key for each role.
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

    # --- ANS (identity_mode=ans) ---
    # The CLI wants ANS_API_KEY="<key>:<secret>"; they stay split here and are
    # composed on demand so the pair is stored in exactly one place.
    ans_base_url: str = "https://api.godaddy.com"
    ans_api_key: str | None = None
    ans_api_secret: str | None = None
    ans_domain: str | None = None
    # Hosts allowed to serve a transparency-log badge. Checked before the badge URL
    # from DNS is fetched, so a forged TXT record cannot redirect the verifier.
    ans_trusted_tl_hosts: str = "api.godaddy.com,transparency.godaddy.com"
    # The authority DPoP htu claims are compared against. Must come from config,
    # never from the request's Host header (ANS-6 §7.4).
    ans_public_base_url: str = "http://127.0.0.1:8000"
    ans_dpop_required: bool = True
    ans_dns_nameservers: str = ""
    ans_badge_ttl_seconds: float = 60.0
    # PEM bundle of the ANS RA's identity-issuing CA. Optional: without it the
    # transparency-log badge is the only trust anchor. Populate from
    # `ans-cli get-identity-certs <agentId>` once an agent is ACTIVE.
    ans_identity_ca_bundle: str | None = None
    # ANS HTTP-01 domain validation: {"<token>": "<keyAuthorization>"} as JSON.
    acme_challenges: str | None = None

    databricks_host: str = ""
    databricks_token: str = ""
    databricks_warehouse_id: str = ""
    databricks_catalog: str = ""
    databricks_schema: str = ""
    databricks_trace_table: str = "synapse_agent_traces"

    # Loopback address the server-side demo runner posts to. Proofs are signed
    # against ans_public_base_url, not this, so the two differ by design.
    local_base_url: str = "http://127.0.0.1:8080"

    @property
    def resolved_database_path(self) -> Path:
        return ROOT / self.database_path

    @property
    def ans_credential(self) -> str | None:
        """The combined `key:secret` form the ANS RA expects."""
        if not self.ans_api_key:
            return None
        if not self.ans_api_secret:
            return self.ans_api_key
        return f"{self.ans_api_key}:{self.ans_api_secret}"

    @property
    def trusted_tl_hosts(self) -> frozenset[str]:
        return frozenset(
            host.strip().lower() for host in self.ans_trusted_tl_hosts.split(",") if host.strip()
        )

    @property
    def dns_nameservers(self) -> list[str]:
        return [ns.strip() for ns in self.ans_dns_nameservers.split(",") if ns.strip()]

    @property
    def databricks_trace_table_name(self) -> str:
        if not self.databricks_catalog or not self.databricks_schema:
            return self.databricks_trace_table
        return f"{self.databricks_catalog}.{self.databricks_schema}.{self.databricks_trace_table}"

    @property
    def live_agents_enabled(self) -> bool:
        return all(
            vendor != "none"
            for vendor in (self.backend_provider, self.frontend_provider, self.qa_provider)
        )

    @property
    def live_integrations(self) -> bool:
        return (
            self.identity_mode != "mock"
            or self.memory_mode != "cache"
            or self.live_agents_enabled
        )
