"""FastAPI application factory.

Changes from Phase 1:
- Added `lifespan` context manager for startup/shutdown lifecycle.
- Registered the notes router at /notes prefix.
- Lifespan shutdown disposes the async engine connection pool cleanly.

The `lifespan` parameter is the FastAPI-recommended lifecycle hook — use it
instead of the older event-registration API.

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
from app.auth.router import router as auth_router
from app.database import engine
from app.notes.router import router as notes_router
from app.tags.router import router as tags_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup → yield → shutdown.

    Startup: no-op in Phase 2 (engine initialised lazily on first request).
    Shutdown: dispose the async engine so all pooled connections are closed
              cleanly — important for graceful container shutdown.
    Future phases will add Qdrant and Ollama client initialisation in startup.
    """
    # -- startup --
    yield
    # -- shutdown --
    await engine.dispose()


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
app.include_router(auth_router, prefix="/auth")
app.include_router(notes_router, prefix="/notes")
app.include_router(tags_router)  # no prefix — owns /tags and /notes/{id}/tags
