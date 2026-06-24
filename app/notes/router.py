"""FastAPI router for Note CRUD endpoints.

Endpoints (all served under the /notes prefix registered in app/main.py):
  GET    /notes/             — paginated list with sort/filter query params
  POST   /notes/             — create a new note (returns 201)
  GET    /notes/{note_id}    — fetch a single note by id (200 or 404)
  PUT    /notes/{note_id}    — partial update (200 or 404)
  DELETE /notes/{note_id}    — delete (204 No Content)

Status codes follow REST conventions:
  200 — OK (read / update)
  201 — Created (create)
  204 — No Content (delete)
  404 — Note not found
  422 — Validation error (Pydantic / FastAPI auto-generated)

Query params for GET /notes/:
  page   — 1-indexed page number (ge=1)
  size   — records per page (ge=1, le=100); >100 yields 422 automatically (D-05)
  sort   — sort expression; leading '-' = descending, default '-created_at'
  filter — optional substring match on content (LIKE %term%)

Phase 2 note: no auth guard — all notes are publicly accessible.
              user_id and current_user injection are added in Phase 3.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteListResponse, NoteRead, NoteUpdate
from app.notes.service import NoteService

router = APIRouter(tags=["notes"])


def _make_service(session: AsyncSession) -> NoteService:
    """Construct NoteService with its repository for the current request session."""
    return NoteService(NoteRepository(session))


@router.get(
    "/",
    response_model=NoteListResponse,
    summary="List notes (paginated)",
    description=(
        "Returns a paginated list of notes. Use `page` and `size` for pagination, "
        "`sort` for sort order (prefix with '-' for descending), "
        "and `filter` for a case-insensitive substring match on content."
    ),
)
async def list_notes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("-created_at"),
    filter: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> NoteListResponse:
    """GET /notes/ — returns paginated notes."""
    return await _make_service(session).list_notes(page=page, size=size, sort=sort, filter=filter)


@router.post(
    "/",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
)
async def create_note(
    data: NoteCreate,
    session: AsyncSession = Depends(get_db),
) -> NoteRead:
    """POST /notes/ — create a new note and return it."""
    note = await _make_service(session).create(data)
    return NoteRead.model_validate(note)


@router.get(
    "/{note_id}",
    response_model=NoteRead,
    summary="Get a note by id",
    responses={404: {"description": "Note not found"}},
)
async def get_note(
    note_id: int,
    session: AsyncSession = Depends(get_db),
) -> NoteRead:
    """GET /notes/{note_id} — fetch a single note or return 404."""
    note = await _make_service(session).get_or_404(note_id)
    return NoteRead.model_validate(note)


@router.put(
    "/{note_id}",
    response_model=NoteRead,
    summary="Update a note",
    responses={404: {"description": "Note not found"}},
)
async def update_note(
    note_id: int,
    data: NoteUpdate,
    session: AsyncSession = Depends(get_db),
) -> NoteRead:
    """PUT /notes/{note_id} — partially update a note or return 404."""
    note = await _make_service(session).update(note_id, data)
    return NoteRead.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    responses={404: {"description": "Note not found"}},
)
async def delete_note(
    note_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """DELETE /notes/{note_id} — delete a note or return 404."""
    await _make_service(session).delete(note_id)
