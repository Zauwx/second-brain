"""FastAPI router for Note CRUD endpoints.

Endpoints:
  GET    /notes              — paginated list with sort/filter query params
  POST   /notes              — create a new note (returns 201)
  GET    /notes/{note_id}    — fetch a single note by id (200 or 404)
  PUT    /notes/{note_id}    — partial update (200 or 404)
  DELETE /notes/{note_id}    — delete (204 No Content)

Status codes follow REST conventions:
  200 — OK (read / update)
  201 — Created (create)
  204 — No Content (delete)
  404 — Note not found
  422 — Validation error (Pydantic / FastAPI auto-generated)

Phase 2 note: no auth guard — all notes are publicly accessible.
              user_id and current_user injection are added in Phase 3.
"""

from typing import Literal

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_note_service
from app.notes.schemas import NoteCreate, NoteRead, NoteUpdate, PaginatedNotes
from app.notes.service import NoteService

router = APIRouter(tags=["notes"])


@router.get(
    "",
    response_model=PaginatedNotes,
    summary="List notes (paginated)",
    description=(
        "Returns a paginated list of notes. Use `page` and `page_size` for pagination, "
        "`sort` for the sort column, and `order` for sort direction."
    ),
)
async def list_notes(
    page: int = 1,
    page_size: int = 20,
    sort: Literal["created_at", "updated_at", "id"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    svc: NoteService = Depends(get_note_service),
) -> PaginatedNotes:
    """GET /notes — returns paginated notes."""
    return await svc.list_notes(page=page, page_size=page_size, sort=sort, order=order)


@router.post(
    "",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
)
async def create_note(
    data: NoteCreate,
    svc: NoteService = Depends(get_note_service),
) -> NoteRead:
    """POST /notes — create a new note and return it."""
    note = await svc.create_note(data)
    return NoteRead.model_validate(note)


@router.get(
    "/{note_id}",
    response_model=NoteRead,
    summary="Get a note by id",
    responses={404: {"description": "Note not found"}},
)
async def get_note(
    note_id: int,
    svc: NoteService = Depends(get_note_service),
) -> NoteRead:
    """GET /notes/{note_id} — fetch a single note or return 404."""
    note = await svc.get_note_or_404(note_id)
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
    svc: NoteService = Depends(get_note_service),
) -> NoteRead:
    """PUT /notes/{note_id} — partially update a note or return 404."""
    note = await svc.update_note(note_id, data)
    return NoteRead.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    responses={404: {"description": "Note not found"}},
)
async def delete_note(
    note_id: int,
    svc: NoteService = Depends(get_note_service),
) -> None:
    """DELETE /notes/{note_id} — delete a note or return 404."""
    await svc.delete_note(note_id)
