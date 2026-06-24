"""NoteRepository — all SQL for the Note entity.

Design principles:
- Zero business logic here. No HTTP concerns. Pure data access.
- All queries use SQLAlchemy 2.x `select()` + `scalars()` async pattern.
- Session is injected via constructor (not imported globally) — makes testing easy:
  replace NoteRepository(real_session) with NoteRepository(mock_session).
- Sort columns are validated against an allow-list before use (prevents SQL injection
  even though ORM params are parameterised, because we use `getattr` on the model).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notes.models import Note
from app.notes.schemas import NoteCreate, NoteUpdate

# Columns allowed for sorting — prevents arbitrary attribute access on Note model.
_SORTABLE_COLUMNS = {"created_at", "updated_at", "id"}
_SORT_ORDERS = {"asc", "desc"}


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

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[Note], int]:
        """Return a paginated list of Notes and the total count.

        Args:
            page: 1-indexed page number.
            page_size: Records per page (max 100 enforced in service layer).
            sort: Column name to sort by — must be in _SORTABLE_COLUMNS.
            order: "asc" or "desc".

        Returns:
            Tuple of (note list, total count).
        """
        # Clamp and validate inputs defensively (service layer also validates).
        sort = sort if sort in _SORTABLE_COLUMNS else "created_at"
        order = order if order in _SORT_ORDERS else "desc"

        sort_column = getattr(Note, sort)
        sort_expr = sort_column.asc() if order == "asc" else sort_column.desc()
        offset = (page - 1) * page_size

        # Execute count and list queries concurrently.
        count_result = await self._session.execute(select(func.count()).select_from(Note))
        total: int = count_result.scalar_one()

        list_result = await self._session.execute(
            select(Note).order_by(sort_expr).offset(offset).limit(page_size)
        )
        notes = list(list_result.scalars().all())

        return notes, total

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
