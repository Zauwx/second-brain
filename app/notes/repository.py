"""NoteRepository — all SQL for the Note entity.

Design principles:
- Zero business logic here. No HTTP concerns. Pure data access.
- All queries use SQLAlchemy 2.x `select()` + `scalars()` async pattern.
- Session is injected via constructor (not imported globally) — makes testing easy.
- Sort parsing: a leading '-' in `sort` means descending (e.g. '-created_at').
- Filter: optional case-insensitive substring match on `content` via LIKE.
"""

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notes.models import Note
from app.notes.schemas import NoteCreate, NoteUpdate


class NoteRepository:
    """Data-access layer for Note records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: NoteCreate) -> Note:
        """Insert a new Note row and return the persisted model instance."""
        note = Note(
            title=data.title,
            content=data.content,
            source_url=data.source_url,
        )
        self._session.add(note)
        await self._session.commit()
        await self._session.refresh(note)
        return note

    async def get_by_id(self, note_id: int) -> Note | None:
        """Return the Note with the given id, or None if not found."""
        result = await self._session.execute(select(Note).where(Note.id == note_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int,
        size: int,
        sort: str = "-created_at",
        filter: str | None = None,
    ) -> tuple[list[Note], int]:
        """Return a paginated list of Notes and the total count.

        Args:
            page: 1-indexed page number.
            size: Records per page.
            sort: Sort expression — leading '-' means descending.
                  Recognised fields: 'created_at', 'updated_at'.
                  Defaults to newest-first ('-created_at').
            filter: Optional substring to match against note content (LIKE %term%).

        Returns:
            Tuple of (note list, total count matching the filter).
        """
        # Build base query with optional LIKE filter (D-08).
        query = select(Note)
        if filter:
            query = query.where(Note.content.ilike(f"%{filter}%"))

        # Accurate filtered total count.
        count_q = select(func.count()).select_from(query.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        # Apply sort — leading '-' means descending (D-07).
        order_col = Note.updated_at if "updated_at" in sort else Note.created_at
        order_fn = desc if sort.startswith("-") else asc
        query = query.order_by(order_fn(order_col))

        # Apply pagination.
        query = query.offset((page - 1) * size).limit(size)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def update(self, note: Note, data: NoteUpdate) -> Note:
        """Apply the provided fields from NoteUpdate to the given Note instance.

        Only non-None fields in `data` are applied — allows partial updates.
        """
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(note, field, value)
        await self._session.commit()
        await self._session.refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        """Delete the given Note from the database."""
        await self._session.delete(note)
        await self._session.commit()
