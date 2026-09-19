from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.app.config import Settings
from server.app.models import Health, WorkspaceState
from server.app.store import read_state


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Synapse API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(identity_mode=settings.identity_mode, memory_mode=settings.memory_mode)

    @app.get("/state", response_model=WorkspaceState)
    def state() -> WorkspaceState:
        return read_state(settings.resolved_database_path)

    return app


app = create_app()
