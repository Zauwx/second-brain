"""Full-text search repository.

Issues MATCH ... AGAINST ... IN BOOLEAN MODE queries against the
ft_notes_content FULLTEXT index on (title, content).

Security properties (T-04-inj):
- `match(against=q)` binds `q` as a SQL parameter — no string interpolation,
  no SQL injection risk (unlike text() with f-strings).
- User-scoped: `.where(Note.user_id == user_id)` enforced on every query (T-04-iso).

Key import: `from sqlalchemy.dialects.mysql import match`
  NOT `func.match()` — the func.* variant lacks the `.in_boolean_mode()` method.
  NOT `text()` with f-string — that bypasses parameterization.
"""

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import match
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.notes.models import Note


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_fulltext(
        self, q: str, user_id: int, page: int = 1, size: int = 20
    ) -> tuple[list[Note], int]:
        """FULLTEXT BOOLEAN MODE search on (title, content), scoped to user_id.

        Args:
            q: Pre-sanitized BOOLEAN MODE search string (from SearchService).
            user_id: Scope results to notes owned by this user (T-04-iso).
            page: 1-indexed page number.
            size: Results per page.

        Returns:
            (notes, total) — notes on the requested page, total matching count.

        Generated SQL (parameterized):
            SELECT notes.* FROM notes
            WHERE MATCH (notes.title, notes.content) AGAINST (%s IN BOOLEAN MODE)
              AND notes.user_id = %s
            LIMIT %s OFFSET %s
        """
        match_expr = match(Note.title, Note.content, against=q).in_boolean_mode()  # type: ignore[arg-type]
        base = (
            select(Note)
            .where(match_expr)
            .where(Note.user_id == user_id)
            .options(selectinload(Note.tags))
        )
        total = (
            await self._session.execute(
                select(func.count()).select_from(base.subquery())
            )
        ).scalar_one()
        result = await self._session.execute(
            base.offset((page - 1) * size).limit(size)
        )
        return list(result.scalars().all()), total
