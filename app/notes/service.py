"""NoteService — business logic for the Note domain.

Responsibilities:
- Orchestrate NoteRepository calls.
- Enforce business rules (404 on missing notes).
- Translate NotFound to HTTPException (HTTP concern handled here, not in repository).
- Return domain objects (Note ORM instances) — the router handles serialisation.

Phase 2 note: no user_id filtering — that is added in Phase 3 with auth.
"""

from fastapi import HTTPException, status

from app.notes.models import Note
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteListResponse, NoteUpdate


class NoteService:
    """Service layer for Note CRUD operations."""

    def __init__(self, repo: NoteRepository) -> None:
        self._repo = repo

    async def create(self, data: NoteCreate) -> Note:
        """Create and persist a new note."""
        return await self._repo.create(data)

    async def get_or_404(self, note_id: int) -> Note:
        """Return the note with the given id, or raise HTTP 404."""
        note = await self._repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        return note

    async def list_notes(
        self,
        page: int = 1,
        size: int = 20,
        sort: str = "-created_at",
        filter: str | None = None,
    ) -> NoteListResponse:
        """Return a paginated list of notes.

        Args:
            page: 1-indexed page number.
            size: Records per page (bounded by router — Query le=100).
            sort: Sort expression (leading '-' = descending).
            filter: Optional substring match on note content.

        Returns:
            NoteListResponse envelope with {items, total, page, size, pages}.
        """
        items, total = await self._repo.list_paginated(page, size, sort, filter)
        pages = (total + size - 1) // size if total > 0 else 0
        return NoteListResponse(items=items, total=total, page=page, size=size, pages=pages)

    async def update(self, note_id: int, data: NoteUpdate) -> Note:
        """Update the note with the given id, or raise HTTP 404.

        Partial update: only fields set in `data` (non-null in request) are applied.
        """
        note = await self.get_or_404(note_id)
        return await self._repo.update(note, data)

    async def delete(self, note_id: int) -> None:
        """Delete the note with the given id, or raise HTTP 404."""
        note = await self.get_or_404(note_id)
        await self._repo.delete(note)
