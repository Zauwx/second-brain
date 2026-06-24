"""NoteService — business logic for the Note domain.

Responsibilities:
- Orchestrate NoteRepository calls.
- Enforce business rules (404 on missing notes, page_size cap).
- Translate NotFound to HTTPException (HTTP concern handled here, not in repository).
- Return domain objects (Note ORM instances) — the router handles serialisation.

Phase 2 note: no user_id filtering — that is added in Phase 3 with auth.
"""

from fastapi import HTTPException, status

from app.notes.models import Note
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteUpdate, PaginatedNotes

# Maximum allowed page_size to prevent DoS via huge page requests.
MAX_PAGE_SIZE = 100


class NoteService:
    """Service layer for Note CRUD operations."""

    def __init__(self, repo: NoteRepository) -> None:
        self._repo = repo

    async def create_note(self, data: NoteCreate) -> Note:
        """Create and persist a new note."""
        return await self._repo.create(data)

    async def get_note_or_404(self, note_id: int) -> Note:
        """Return the note with the given id, or raise HTTP 404."""
        note = await self._repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Note {note_id} not found",
            )
        return note

    async def list_notes(
        self,
        page: int = 1,
        page_size: int = 20,
        sort: str = "created_at",
        order: str = "desc",
    ) -> PaginatedNotes:
        """Return a paginated list of notes.

        Args:
            page: 1-indexed page number (clamped to minimum 1).
            page_size: Records per page (clamped to [1, MAX_PAGE_SIZE]).
            sort: Column to sort by — repository validates against allow-list.
            order: "asc" or "desc" — repository validates.

        Returns:
            PaginatedNotes with items, total, page, and page_size.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))

        notes, total = await self._repo.list_all(page, page_size, sort, order)
        return PaginatedNotes(
            items=notes,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_note(self, note_id: int, data: NoteUpdate) -> Note:
        """Update the note with the given id, or raise HTTP 404.

        Partial update: only fields set in `data` (non-null in request) are applied.
        """
        note = await self.get_note_or_404(note_id)
        return await self._repo.update(note, data)

    async def delete_note(self, note_id: int) -> None:
        """Delete the note with the given id, or raise HTTP 404."""
        note = await self.get_note_or_404(note_id)
        await self._repo.delete(note)
