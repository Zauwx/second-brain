"""Shared FastAPI dependency providers.

These functions are injected into route handlers via `Depends()`.
Centralising them here avoids importing from multiple modules and makes
dependency overrides in tests cleaner (one place to patch).

Usage:
    from fastapi import Depends
    from app.core.dependencies import get_db, get_note_service

    @router.get("/notes")
    async def list_notes(svc: NoteService = Depends(get_note_service)):
        ...
"""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.notes.repository import NoteRepository
from app.notes.service import NoteService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; close it cleanly on response completion."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_note_service(
    db: AsyncSession = Depends(get_db),
) -> NoteService:
    """Construct NoteService with its repository for the current request."""
    return NoteService(NoteRepository(db))
