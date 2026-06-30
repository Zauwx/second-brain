"""FastAPI router for Note CRUD endpoints.

Endpoints (all served under the /notes prefix registered in app/main.py):
  GET    /notes/             — paginated list with sort/filter query params
  POST   /notes/             — create a new note (returns 201)
  GET    /notes/{note_id}    — fetch a single note by id (200 or 404)
  PUT    /notes/{note_id}    — partial update (200 or 404 or 403)
  DELETE /notes/{note_id}    — delete (204 No Content)

All endpoints require a valid Bearer access token (Phase 3 — get_current_user dependency).
Missing or invalid token returns 401. Cross-user access returns 403. Missing id returns 404.

Status codes follow REST conventions:
  200 — OK (read / update)
  201 — Created (create)
  204 — No Content (delete)
  401 — Missing or invalid access token (get_current_user dependency)
  403 — Authenticated but accessing another user's note (ownership check)
  404 — Note not found
  422 — Validation error (Pydantic / FastAPI auto-generated)

Query params for GET /notes/:
  page   — 1-indexed page number (ge=1)
  size   — records per page (ge=1, le=100); >100 yields 422 automatically (D-05)
  sort   — sort expression; leading '-' = descending, default '-created_at'
  filter — optional substring match on content (LIKE %term%)
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.dependencies import get_current_user, get_db
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
        "Returns a paginated list of the authenticated user's notes. "
        "Use `page` and `size` for pagination, "
        "`sort` for sort order (prefix with '-' for descending), "
        "`filter` for a case-insensitive substring match on content, "
        "and `tag` (repeatable) for AND-intersection tag filtering. "
        "Requires a valid Bearer access token — 401 if missing or invalid."
    ),
)
async def list_notes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("-created_at"),
    filter: str | None = Query(None),
    tag: list[str] | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    """GET /notes/ — returns paginated notes owned by the authenticated user (D-09)."""
    return await _make_service(session).list_notes(
        page=page, size=size, sort=sort, filter=filter, tags=tag, user_id=current_user.id
    )


@router.post(
    "/",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
)
async def create_note(
    data: NoteCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """POST /notes/ — create a new note owned by the authenticated user (D-10).

    user_id is assigned server-side from the access token; it is never accepted
    from the request body. Any user_id field in the request body is silently ignored
    because NoteCreate does not include user_id.
    """
    note = await _make_service(session).create(data, user_id=current_user.id)
    return NoteRead.model_validate(note)


@router.get(
    "/{note_id}",
    response_model=NoteRead,
    summary="Get a note by id",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note exists but is owned by another user"},
        404: {"description": "Note not found"},
    },
)
async def get_note(
    note_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """GET /notes/{note_id} — fetch a single note; 404 if missing, 403 if wrong owner (D-08)."""
    note = await _make_service(session).get_or_404_owned(note_id, current_user)
    return NoteRead.model_validate(note)


@router.put(
    "/{note_id}",
    response_model=NoteRead,
    summary="Update a note",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note exists but is owned by another user"},
        404: {"description": "Note not found"},
    },
)
async def update_note(
    note_id: int,
    data: NoteUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """PUT /notes/{note_id} — partially update a note; 404 if missing, 403 if wrong owner."""
    note = await _make_service(session).update(note_id, data, current_user)
    return NoteRead.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note exists but is owned by another user"},
        404: {"description": "Note not found"},
    },
)
async def delete_note(
    note_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """DELETE /notes/{note_id} — delete a note; 404 if missing, 403 if wrong owner."""
    await _make_service(session).delete(note_id, current_user)
