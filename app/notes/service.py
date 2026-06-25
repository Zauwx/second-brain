"""NoteService — business logic for the Note domain.

Responsibilities:
- Orchestrate NoteRepository calls.
- Enforce business rules (404 on missing notes, 403 on ownership violations).
- Translate repository exceptions to HTTPException (HTTP concern handled here, not in repo).
- Return domain objects (Note ORM instances) — the router handles serialisation.

Phase 3 additions (D-07..D-10):
- create(data, user_id) — user_id is assigned server-side (D-10)
- get_or_404_owned(note_id, current_user) — 404 if missing, 403 if wrong owner (D-08)
- list_notes(..., user_id) — lists are scoped to the authenticated owner (D-09)
- update/delete use get_or_404_owned instead of get_or_404
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.notes.models import Note
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteListResponse, NoteRead, NoteUpdate

if TYPE_CHECKING:
    from app.auth.models import User


class NoteService:
    """Service layer for Note CRUD operations."""

    def __init__(self, repo: NoteRepository) -> None:
        self._repo = repo

    async def create(self, data: NoteCreate, user_id: int) -> Note:
        """Create and persist a new note assigned to `user_id` (D-10).

        user_id is always set server-side from the authenticated user's id;
        it is never accepted from the client request body.
        """
        return await self._repo.create(data, user_id)

    async def get_or_404(self, note_id: int) -> Note:
        """Return the note with the given id, or raise HTTP 404.

        Does NOT check ownership — use get_or_404_owned for authenticated endpoints.
        Kept for internal use only.
        """
        note = await self._repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        return note

    async def get_or_404_owned(self, note_id: int, current_user: User) -> Note:
        """Return the note or raise 404 (missing) / 403 (wrong owner) (D-08).

        Sequence per RESEARCH.md Pattern 4:
          1. Fetch by PK (no owner filter in the repository — ownership is a service concern).
          2. If None → 404 "Note not found".
          3. If note.user_id != current_user.id → 403 "Access forbidden".
          4. Else → return the note.

        This implements the explicit ownership check rather than 404-hiding — a deliberate
        choice for teachable HTTP semantics (D-08, T-03-21).
        """
        note = await self._repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        if note.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden",
            )
        return note

    async def list_notes(
        self,
        page: int = 1,
        size: int = 20,
        sort: str = "-created_at",
        filter: str | None = None,
        *,
        user_id: int,
    ) -> NoteListResponse:
        """Return a paginated list of notes owned by `user_id` (D-09).

        Args:
            page:    1-indexed page number.
            size:    Records per page (bounded by router — Query le=100).
            sort:    Sort expression (leading '-' = descending).
                     Unknown sort fields yield HTTP 422 (D-07/D-09, T-02-11/T-02-14).
            filter:  Optional substring match on note content.
            user_id: Scope results to this owner — keyword-only to prevent positional errors.

        Returns:
            NoteListResponse envelope with {items, total, page, size, pages}.

        Raises:
            HTTPException 422: When the repository raises ValueError for an invalid sort field.
        """
        try:
            items, total = await self._repo.list_paginated(
                page, size, sort, filter, user_id=user_id
            )
        except ValueError as exc:
            # Repository raises ValueError for unknown sort tokens (D-07, T-02-11).
            # Translate to a clean 422 — do not let a 500 leak internals (T-02-14).
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        pages = (total + size - 1) // size if total > 0 else 0
        return NoteListResponse(
            items=[NoteRead.model_validate(n) for n in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def update(self, note_id: int, data: NoteUpdate, current_user: User) -> Note:
        """Update the note with the given id, or raise 404/403.

        Uses get_or_404_owned to enforce ownership before mutating (D-08).
        Partial update: only fields set in `data` (non-null in request) are applied.
        """
        note = await self.get_or_404_owned(note_id, current_user)
        return await self._repo.update(note, data)

    async def delete(self, note_id: int, current_user: User) -> None:
        """Delete the note with the given id, or raise 404/403.

        Uses get_or_404_owned to enforce ownership before deletion (D-08).
        """
        note = await self.get_or_404_owned(note_id, current_user)
        await self._repo.delete(note)
