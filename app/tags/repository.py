"""TagRepository — all SQL for the Tag entity.

Design principles (mirror NoteRepository):
- Zero business logic. No HTTP concerns. Pure data access.
- Session injected via constructor.

Key patterns:
- find_or_create: normalize name, SELECT existing, else INSERT with SAVEPOINT.
  Uses begin_nested() (savepoint) — NOT bare rollback() — to handle concurrent
  inserts without destroying the outer test transaction (Pitfall 4, RESEARCH.md).
- attach/detach via ORM relationship append/remove + flush.
  SQLAlchemy manages note_tags rows; no manual INSERT/DELETE needed.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.notes.models import Note
from app.tags.models import Tag


class TagRepository:
    """Data-access layer for Tag records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create(self, user_id: int, raw_name: str) -> Tag:
        """Find or create a Tag for this user, normalized (D-01, D-03).

        Normalizes raw_name via strip().lower() before looking up or inserting.
        Uses a SAVEPOINT (begin_nested) to handle the race-condition window between
        SELECT (not found) and INSERT (concurrent request wins the UNIQUE constraint).

        Args:
            user_id:  The owning user's id — tags are per-user (D-02).
            raw_name: The raw tag name from the client — normalized server-side.

        Returns:
            The existing or newly-created Tag.
        """
        name = raw_name.strip().lower()  # D-03: normalize at write time

        # Optimistic path — common case, no contention
        existing = (
            await self._session.execute(
                select(Tag).where(Tag.user_id == user_id, Tag.name == name)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        tag = Tag(user_id=user_id, name=name)
        try:
            async with self._session.begin_nested():  # SAVEPOINT — not rollback()
                self._session.add(tag)
            return tag
        except IntegrityError:
            # Concurrent request won the race; savepoint rolled back, outer tx intact
            return (
                await self._session.execute(
                    select(Tag).where(Tag.user_id == user_id, Tag.name == name)
                )
            ).scalar_one()

    async def get_by_name(self, user_id: int, raw_name: str) -> Tag | None:
        """Return the Tag for this user with the normalized name, or None."""
        name = raw_name.strip().lower()
        return (
            await self._session.execute(
                select(Tag).where(Tag.user_id == user_id, Tag.name == name)
            )
        ).scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> list[Tag]:
        """Return all tags owned by user_id, ordered by name."""
        result = await self._session.execute(
            select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
        )
        return list(result.scalars().all())

    async def attach(self, note: Note, tag: Tag) -> None:
        """Attach a tag to a note (idempotent — no-op if already attached).

        ORM manages the note_tags join-table row; no manual INSERT needed.
        Flush ensures the row is visible to subsequent queries in the same transaction.
        """
        if tag not in note.tags:
            note.tags.append(tag)
        await self._session.flush()

    async def detach(self, note: Note, tag: Tag) -> None:
        """Detach a tag from a note.

        ORM manages the note_tags row deletion on flush.
        Caller is responsible for verifying the tag is actually attached.
        """
        note.tags.remove(tag)
        await self._session.flush()
