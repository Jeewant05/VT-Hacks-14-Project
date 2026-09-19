from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.app.adapters import CacheMemory, IdentityAdapter, MemoryAdapter, MockIdentity
from server.app.config import Settings
from server.app.live_agents import LiveRuns
from server.app.live_routes import build_live_router
from server.app.models import Health, WorkspaceState
from server.app.routes import build_router
from server.app.service import Coordinator
from server.app.store import read_state


def _fresh_state() -> WorkspaceState:
    from scripts.database import demo_state

    return demo_state()


def build_identity(settings: Settings) -> IdentityAdapter:
    if settings.identity_mode == "ans":
        from server.app.identity_ans import AnsIdentity  # P4 owns this file

        return AnsIdentity(settings)
    return MockIdentity()


def build_memory(settings: Settings) -> MemoryAdapter:
    seeded = read_state(settings.resolved_database_path).decisions
    if settings.memory_mode == "databricks":
        from server.app.memory_databricks import DatabricksMemory  # P3 owns this file

        return DatabricksMemory(settings, fallback=CacheMemory(seeded))
    return CacheMemory(seeded)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Synapse API", version="0.4.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    coordinator = Coordinator(
        settings.resolved_database_path, build_identity(settings), build_memory(settings)
    )

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(
            identity_mode=settings.identity_mode,
            memory_mode=settings.memory_mode,
            live_integrations=settings.live_integrations,
        )

    @app.get("/state", response_model=WorkspaceState)
    def state() -> WorkspaceState:
        return read_state(settings.resolved_database_path)

    app.include_router(build_router(coordinator, _fresh_state))
    providers = {}
    if settings.agent_provider == "gemini":
        from server.app.gemini import GeminiProvider

        providers = {
            role: GeminiProvider(settings, key)
            for role, key in settings.gemini_agent_api_keys.items()
            if key
        }
    runs = LiveRuns(providers, settings.resolved_database_path.parent / "live-runs")
    app.include_router(build_live_router(runs, settings.gemini_model))
    return app


app = create_app()
