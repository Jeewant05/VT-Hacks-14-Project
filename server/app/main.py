from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.app.adapters import CacheMemory, MockIdentity
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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Synapse API", version="0.3.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["GET", "POST"], allow_headers=["*"])
    identity = MockIdentity()
    memory = CacheMemory(read_state(settings.resolved_database_path).decisions)
    coordinator = Coordinator(settings.resolved_database_path, identity, memory)

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(identity_mode=settings.identity_mode, memory_mode=settings.memory_mode)

    @app.get("/state", response_model=WorkspaceState)
    def state() -> WorkspaceState:
        return read_state(settings.resolved_database_path)

    app.include_router(build_router(coordinator, _fresh_state))
    if settings.agent_provider == "gemini" and settings.gemini_api_key:
        from server.app.gemini import GeminiProvider
        app.include_router(build_live_router(LiveRuns(GeminiProvider(settings), settings.resolved_database_path.parent / "live-runs")))
    return app


app = create_app()
