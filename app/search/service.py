"""Full-text search service.

Sanitizes user-supplied BOOLEAN MODE queries before passing to the repository,
preventing InnoDB errors from malformed operator sequences (T-04-inj, T-04-08).
"""

import re

from app.notes.schemas import NoteListResponse, NoteRead
from app.search.repository import SearchRepository


def sanitize_boolean_query(q: str) -> str | None:
    """Sanitize user input for MATCH ... AGAINST ... IN BOOLEAN MODE.

    InnoDB BOOLEAN MODE raises errors for several special characters
    (dev.mysql.com/doc/refman/8.4/en/fulltext-boolean.html).  Beyond `+ - @`,
    an unbalanced phrase quote (`"`), grouping paren (`(` `)`), rank-negation
    (`~`), contribution operators (`<` `>`), or a lone truncation `*` all raise
    an InnoDB syntax error that would otherwise surface as a 500 (WR-01).

    Strategy: whitelist. Keep only word characters, whitespace, and the operators
    we actually support (`+ - *`); replace everything else with a space. Then
    clean up operator sequences so the result is always a valid BOOLEAN MODE
    expression:

    - Strips leading/trailing whitespace; returns None if empty (skip DB call).
    - Drops any character outside [word chars, whitespace, + - *] — this removes
      `" ( ) ~ < > @` and any other punctuation that can trigger a parse error.
    - Removes consecutive operator sequences (++, +-, -+, --).
    - Removes trailing operators attached to a token (word+ → word; word* kept).
    - Removes a standalone/leading `*` (truncation operator with no preceding
      token is a syntax error).
    - Collapses internal whitespace.

    Returns:
        Cleaned query string, or None if the result is empty.  Callers MUST
        return an empty NoteListResponse when None is returned — do not call
        the repository.
    """
    q = q.strip()
    if not q:
        return None
    # Whitelist: keep word chars (incl. unicode for utf8mb4), whitespace, and the
    # supported boolean operators (+ - *). Everything else — " ( ) ~ < > @ etc. —
    # becomes a space so an unbalanced quote/paren can never reach InnoDB.
    q = re.sub(r"[^\w\s+\-*]", " ", q, flags=re.UNICODE)
    # Remove consecutive operators: ++, +-, -+, --
    q = re.sub(r"[+\-]{2,}", "", q)
    # Remove trailing +/- operators attached to a word token (word+ → word)
    q = re.sub(r"(\w|\*)[+\-]+(?=\s|$)", r"\1", q)
    # Remove a leading/standalone '*' (truncation needs a preceding token)
    q = re.sub(r"(^|\s)\*+", r"\1", q)
    # Collapse whitespace
    q = re.sub(r"\s+", " ", q).strip()
    return q or None


class SearchService:
    def __init__(self, repo: SearchRepository) -> None:
        self._repo = repo

    async def search(
        self, q: str, page: int, size: int, user_id: int
    ) -> NoteListResponse:
        """Sanitize query and execute FULLTEXT search, returning paginated envelope.

        Short-circuits to an empty envelope when the sanitized query is empty —
        avoids a useless DB round-trip and guarantees 200 (not 500) for inputs
        that consist entirely of operator characters (T-04-08).
        """
        clean_q = sanitize_boolean_query(q)
        if clean_q is None:
            return NoteListResponse(items=[], total=0, page=page, size=size, pages=0)
        items, total = await self._repo.search_fulltext(clean_q, user_id, page, size)
        pages = (total + size - 1) // size if total > 0 else 0
        return NoteListResponse(
            items=[NoteRead.model_validate(n) for n in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )
