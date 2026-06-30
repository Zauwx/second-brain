"""CollectionService — business logic for the Collection domain.

Responsibilities:
- Orchestrate CollectionRepository and NoteRepository calls.
- Enforce business rules: 404 on missing collection, 403 on ownership violations (T-04-iso).
- Return domain objects or NoteListResponse envelope; router handles serialisation.

get_or_404_owned mirrors NoteService.get_or_404_owned (D-08, T-04-iso).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.collections.models import Collection
from app.collections.repository import CollectionRepository
from app.collections.schemas import CollectionCreate
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteListResponse, NoteRead

if TYPE_CHECKING:
    from app.auth.models import User


class CollectionService:
    """Service layer for Collection CRUD + note-membership operations."""

    def __init__(self, repo: CollectionRepository, note_repo: NoteRepository) -> None:
        self._repo = repo
        self._note_repo = note_repo

    async def get_or_404_owned(self, collection_id: int, current_user: User) -> Collection:
        """Return the collection or raise 404 (missing) / 403 (wrong owner) (T-04-iso).

        Sequence (mirrors NoteService.get_or_404_owned):
          1. Fetch by PK — no owner filter in repository (D-08).
          2. None → 404 "Collection not found".
          3. collection.user_id != current_user.id → 403 "Access forbidden".
          4. Else → return the collection.
        """
        coll = await self._repo.get_by_id(collection_id)
        if coll is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found",
            )
        if coll.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden",
            )
        return coll

    async def create(self, data: CollectionCreate, user_id: int) -> Collection:
        """Create a new collection for user_id."""
        return await self._repo.create(user_id, data.name)

    async def list_collections(self, user_id: int) -> list[Collection]:
        """Return all collections owned by user_id (T-04-06: scoped to caller)."""
        return await self._repo.list_by_user(user_id)

    async def add_note(
        self, collection_id: int, note_id: int, current_user: User
    ) -> None:
        """Add a note to a collection, verifying ownership of both (T-04-iso).

        Raises:
            HTTPException 404: If collection or note does not exist.
            HTTPException 403: If collection or note is owned by another user.
        """
        coll = await self.get_or_404_owned(collection_id, current_user)

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

        await self._repo.add_note(coll, note)

    async def remove_note(
        self, collection_id: int, note_id: int, current_user: User
    ) -> None:
        """Remove a note from a collection, verifying ownership of the collection.

        Raises:
            HTTPException 404: If collection or note not found / not a member.
            HTTPException 403: If collection is owned by another user.
        """
        coll = await self.get_or_404_owned(collection_id, current_user)

        note = await self._note_repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note not found",
            )
        if note not in coll.notes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Note is not a member of this collection",
            )

        await self._repo.remove_note(coll, note)

    async def list_notes(
        self,
        collection_id: int,
        page: int,
        size: int,
        current_user: User,
    ) -> NoteListResponse:
        """Return a paginated NoteListResponse for the given collection (T-04-06).

        Raises:
            HTTPException 404: If the collection does not exist.
            HTTPException 403: If the collection is owned by another user.
        """
        # Ownership check first (T-04-iso): get_or_404_owned raises 404/403 as needed.
        await self.get_or_404_owned(collection_id, current_user)

        items, total = await self._repo.list_notes(
            collection_id, page, size, user_id=current_user.id
        )
        pages = (total + size - 1) // size if total > 0 else 0
        return NoteListResponse(
            items=[NoteRead.model_validate(n) for n in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )
