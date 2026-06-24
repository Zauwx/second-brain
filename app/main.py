"""FastAPI application factory.

Changes from Phase 1:
- Added `lifespan` context manager for startup/shutdown lifecycle.
- Registered the notes router at /notes prefix.

The `lifespan` pattern (not deprecated `on_startup` / `on_shutdown`) is the
FastAPI-recommended way to run code at startup and shutdown. In this phase,
no explicit startup is needed — the async engine is created lazily when the
first request arrives. Later phases will use lifespan to initialise Qdrant
and Ollama clients.

Database migration note:
  Do NOT run `alembic upgrade head` here. Running migrations in app startup
  causes race conditions when multiple replicas start simultaneously and
  health-check timeouts for slow migrations. Run Alembic as a one-shot step
  before the API starts (e.g., a Docker Compose init service or a CI pre-step).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.notes.router import router as notes_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown.

    Startup: no-op in Phase 2 (engine initialised lazily on first request).
    Shutdown: SQLAlchemy disposes of the connection pool automatically when
              the engine object is garbage-collected; no explicit cleanup needed here.
    Future phases will add Qdrant and Ollama client initialisation in startup.
    """
    # -- startup --
    yield
    # -- shutdown --


app = FastAPI(
    title="Second Brain",
    description=(
        "Self-hosted second brain: save notes, organize with tags, "
        "and query your knowledge in natural language."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(notes_router, prefix="/notes")
