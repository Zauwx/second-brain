"""NoteRepository — all SQL for the Note entity.

Design principles:
- Zero business logic here. No HTTP concerns. Pure data access.
- All queries use SQLAlchemy 2.x `select()` + `scalars()` async pattern.
- Session is injected via constructor (not imported globally) — makes testing easy.
- Sort parsing: a leading '-' in `sort` means descending (e.g. '-created_at').
  Only whitelisted fields are accepted — unknown tokens raise ValueError (D-07, T-02-11).
- Filter: optional case-insensitive substring match on `content` via LIKE (D-08, T-02-12).
- Phase 3: all queries scoped to the authenticated owner via user_id (D-07, D-09, D-10).
"""

from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.notes.models import Note
from app.notes.schemas import NoteCreate, NoteUpdate

# Whitelisted sort fields — maps token to ORM column object (D-07, T-02-11).
# Only these tokens are accepted; anything else raises ValueError → 422.
_SORT_WHITELIST: dict[str, InstrumentedAttribute[datetime]] = {
    "created_at": Note.created_at,
    "updated_at": Note.updated_at,
}


class NoteRepository:
    """Data-access layer for Note records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: NoteCreate, user_id: int) -> Note:
        """Insert a new Note row and return the persisted model instance.

        Args:
            data:    Validated note creation fields (D-10: user_id is NOT in NoteCreate).
            user_id: The owning user's id — assigned server-side, never from the client body.
        """
        note = Note(
            title=data.title,
            content=data.content,
            source_url=data.source_url,
            user_id=user_id,
        )
        self._session.add(note)
        await self._session.commit()
        await self._session.refresh(note)
        return note

    async def get_by_id(self, note_id: int) -> Note | None:
        """Return the Note with the given id, or None if not found.

        Ownership check is NOT performed here — that is the service's responsibility (D-08).
        The repository always fetches by PK only; NoteService.get_or_404_owned checks owner.
        """
        result = await self._session.execute(select(Note).where(Note.id == note_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int,
        size: int,
        sort: str = "-created_at",
        filter: str | None = None,
        *,
        user_id: int,
    ) -> tuple[list[Note], int]:
        """Return a paginated list of Notes owned by `user_id` and the owner-scoped count.

        Args:
            page:    1-indexed page number.
            size:    Records per page.
            sort:    Sort expression — leading '-' means descending.
                     Allowed fields: 'created_at', 'updated_at' (D-07).
                     Defaults to newest-first ('-created_at').
                     Raises ValueError if the field token is not in the whitelist (T-02-11).
            filter:  Optional substring to match against note content (LIKE %term%, D-08).
            user_id: Scope all results to this owner (D-09). Keyword-only to prevent
                     accidental positional misuse.

        Returns:
            Tuple of (note list, total count matching the owner + optional filter).

        Raises:
            ValueError: If `sort` contains a field token not in the whitelist.
        """
        # --- Parse and validate sort parameter (D-07, T-02-11) ---
        # Strip one leading '-' to extract the field token; remainder is direction.
        descending = sort.startswith("-")
        token = sort.lstrip("-")

        if token not in _SORT_WHITELIST:
            raise ValueError(f"invalid sort field: {token!r}")

        order_col = _SORT_WHITELIST[token]
        order_fn = desc if descending else asc

        # --- Build base query scoped to owner (D-09) ---
        # user_id filter must be applied BEFORE the optional content filter so that
        # both the count subquery and the page query are owner-scoped.
        query = select(Note)
        query = query.where(Note.user_id == user_id)
        if filter:
            # ilike() binds the user value as a parameter — the f-string only adds wildcards
            # around an already-escaped bound value, not raw SQL text.
            query = query.where(Note.content.ilike(f"%{filter}%"))

        # --- Accurate filtered total count (BEFORE offset/limit) ---
        # Count is computed over the owner-scoped (+ filtered) subquery so it reflects
        # matches for this user, not the full collection.
        count_q = select(func.count()).select_from(query.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        # --- Apply sort, then pagination ---
        query = query.order_by(order_fn(order_col))
        query = query.offset((page - 1) * size).limit(size)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def update(self, note: Note, data: NoteUpdate) -> Note:
        """Apply the explicitly-set fields from NoteUpdate to the Note instance.

        Uses ``exclude_unset=True``: only fields the client actually sent are
        applied (partial update). An explicitly-sent ``null`` IS included, so
        ``{"title": null}`` clears the column — matching the schema docstring
        "set to null to clear" (WR-06). Omitted fields are left untouched.
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
