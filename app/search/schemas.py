"""Search schemas.

No new response class is defined here — the search endpoint reuses
NoteListResponse from app.notes.schemas (D-06: single canonical envelope).

Query parameters (q, page, size) are declared inline in the router via
FastAPI Query() so they appear correctly in the generated OpenAPI spec.
"""

# Re-export for convenience — callers can import from either location.
from app.notes.schemas import NoteListResponse as NoteListResponse  # noqa: F401
