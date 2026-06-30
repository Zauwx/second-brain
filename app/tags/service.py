"""TagService — business logic for the Tag domain.

Responsibilities:
- Orchestrate TagRepository and NoteRepository calls.
- Enforce business rules: 404 on missing note, 403 on ownership violations.
- Return domain objects; the router handles serialisation.

get_or_404_owned mirrors NoteService.get_or_404_owned exactly (D-08, T-04-iso).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.notes.models import Note
from app.notes.repository import NoteRepository
from app.tags.models import Tag
from app.tags.repository import TagRepository

if TYPE_CHECKING:
    from app.auth.models import User


class TagService:
    """Service layer for Tag CRUD + note-attachment operations."""

    def __init__(self, repo: TagRepository, note_repo: NoteRepository) -> None:
        self._repo = repo
        self._note_repo = note_repo

    async def get_or_404_owned(self, note_id: int, current_user: User) -> Note:
        """Return the note or raise 404 (missing) / 403 (wrong owner) (T-04-iso).

        Mirrors NoteService.get_or_404_owned — copy of the ownership pattern
        so TagService can protect all tag-mutation endpoints.
        """
        note = await self._note_repo.get_by_id(note_id)
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

    async def attach_tag(self, note_id: int, raw_name: str, current_user: User) -> Note:
        """Attach a tag (find-or-create, normalized) to a note the user owns.

        Returns the updated Note with tags eager-loaded so the router can
        serialize NoteRead with a populated `tags` array.

        Steps:
          1. Resolve + own note (404/403).
          2. find_or_create tag for this user (SAVEPOINT-safe, D-01/D-03).
          3. attach (idempotent — no duplicate join-table row).
          4. Re-fetch note via get_by_id so selectinload(Note.tags) is fresh.
        """
        note = await self.get_or_404_owned(note_id, current_user)
        tag = await self._repo.find_or_create(current_user.id, raw_name)
        await self._repo.attach(note, tag)
        # Re-fetch with selectinload to guarantee the response carries full tags list.
        refreshed = await self._note_repo.get_by_id(note_id)
        assert refreshed is not None  # note exists — we just owned it
        return refreshed

    async def detach_tag(self, note_id: int, raw_name: str, current_user: User) -> None:
        """Detach a tag from a note the user owns.

        Raises:
            HTTPException 404: If the note does not exist, or the tag is not attached.
            HTTPException 403: If the note is owned by another user.
        """
        note = await self.get_or_404_owned(note_id, current_user)
        name = raw_name.strip().lower()
        tag = await self._repo.get_by_name(current_user.id, name)
        if tag is None or tag not in note.tags:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tag not found on this note",
            )
        await self._repo.detach(note, tag)

    async def list_tags(self, user_id: int) -> list[Tag]:
        """Return all tags owned by user_id, ordered by name."""
        return await self._repo.list_by_user(user_id)
