from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    identity_mode: Literal["mock", "ans"] = "mock"
    memory_mode: Literal["cache"] = "cache"
    database_path: Path = Path(".local/synapse.db")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    agent_provider: Literal["none", "gemini"] = "none"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

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

    @property
    def resolved_database_path(self) -> Path:
        return ROOT / self.database_path

    @property
    def ans_credential(self) -> str | None:
        """The combined `key:secret` form the ANS RA expects."""
        if not self.ans_api_key:
            return None
        return f"{self.ans_api_key}:{self.ans_api_secret}" if self.ans_api_secret else self.ans_api_key

    @property
    def trusted_tl_hosts(self) -> frozenset[str]:
        return frozenset(
            host.strip().lower() for host in self.ans_trusted_tl_hosts.split(",") if host.strip()
        )

    @property
    def dns_nameservers(self) -> list[str]:
        return [ns.strip() for ns in self.ans_dns_nameservers.split(",") if ns.strip()]
