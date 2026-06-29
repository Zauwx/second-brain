"""CollectionRepository — all SQL for the Collection entity.

Design principles (mirror NoteRepository):
- Zero business logic. No HTTP concerns. Pure data access.
- Session injected via constructor.

Key patterns:
- get_by_id: fetch by PK, no ownership filter — service is responsible for that (D-08).
- create: add + commit + refresh (no re-fetch needed; no relationship to eager-load).
- list_by_user: filter by user_id, ordered by name.
- add_note / remove_note: ORM relationship append/remove + commit.
  SQLAlchemy manages note_collections join-table rows; no manual DML needed.
- list_notes: JOIN via note_collections, filter by collection_id + user_id (T-04-06),
  selectinload(Note.tags) to avoid N+1, returns (list[Note], int) tuple.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collections.models import Collection
from app.notes.models import Note, note_collections


class CollectionRepository:
    """Data-access layer for Collection records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, collection_id: int) -> Collection | None:
        """Return the Collection with the given id, or None if not found.

        Ownership check is NOT performed here — that is the service's responsibility (D-08).
        Collection.notes is eagerly loaded via selectinload so that add_note/remove_note
        can access it without triggering MissingGreenlet in the async context.
        """
        result = await self._session.execute(
            select(Collection)
            .where(Collection.id == collection_id)
            .options(selectinload(Collection.notes))
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, name: str) -> Collection:
        """Insert a new Collection and return the persisted instance."""
        coll = Collection(user_id=user_id, name=name)
        self._session.add(coll)
        await self._session.commit()
        await self._session.refresh(coll)
        return coll

    async def list_by_user(self, user_id: int) -> list[Collection]:
        """Return all collections owned by user_id, ordered by name."""
        result = await self._session.execute(
            select(Collection)
            .where(Collection.user_id == user_id)
            .order_by(Collection.name)
        )
        return list(result.scalars().all())

    async def add_note(self, collection: Collection, note: Note) -> None:
        """Add a note to a collection (idempotent if already member).

        SQLAlchemy manages the note_collections join-table row via the
        Collection.notes relationship on append.
        """
        if note not in collection.notes:
            collection.notes.append(note)
        await self._session.commit()

    async def remove_note(self, collection: Collection, note: Note) -> None:
        """Remove a note from a collection.

        Caller is responsible for verifying the note is actually a member.
        """
        collection.notes.remove(note)
        await self._session.commit()

    async def list_notes(
        self,
        collection_id: int,
        page: int,
        size: int,
        *,
        user_id: int,
    ) -> tuple[list[Note], int]:
        """Return a paginated list of notes in the given collection, scoped to user_id.

        Double-scoped by both collection_id (via join on note_collections) and
        user_id (via Note.user_id) to enforce T-04-06 / T-04-iso isolation.
        selectinload(Note.tags) prevents N+1 and MissingGreenlet in async context.

        Returns:
            Tuple of (note list for this page, total matching count).
        """
        query = (
            select(Note)
            .join(note_collections, Note.id == note_collections.c.note_id)
            .where(note_collections.c.collection_id == collection_id)
            .where(Note.user_id == user_id)
            .options(selectinload(Note.tags))
        )
        count_q = select(func.count()).select_from(query.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()
        result = await self._session.execute(
            query.offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total
