"""FastAPI router for Collection endpoints.

Endpoints (all served under the /collections prefix registered in app/main.py):
  POST   /collections/                    — create a new collection (201)
  GET    /collections/                    — list caller's collections
  POST   /collections/{id}/notes          — add a note to a collection (204)
  DELETE /collections/{id}/notes/{note_id} — remove a note from a collection (204)
  GET    /collections/{id}/notes          — list a collection's notes (NoteListResponse)

All endpoints require a valid Bearer access token (get_current_user dependency — 401).
Cross-user access returns 403. Missing resource returns 404.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.collections.repository import CollectionRepository
from app.collections.schemas import CollectionCreate, CollectionRead, NoteAddBody
from app.collections.service import CollectionService
from app.core.dependencies import get_current_user, get_db
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteListResponse

router = APIRouter(tags=["collections"])


def _make_service(session: AsyncSession) -> CollectionService:
    """Construct CollectionService with its repositories for the current request session."""
    return CollectionService(CollectionRepository(session), NoteRepository(session))


@router.post(
    "/",
    response_model=CollectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a collection",
)
async def create_collection(
    data: CollectionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionRead:
    """POST /collections/ — create a new collection owned by the authenticated user."""
    coll = await _make_service(session).create(data, user_id=current_user.id)
    return CollectionRead.model_validate(coll)


@router.get(
    "/",
    response_model=list[CollectionRead],
    summary="List collections",
)
async def list_collections(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CollectionRead]:
    """GET /collections/ — list all collections owned by the authenticated user (T-04-06)."""
    collections = await _make_service(session).list_collections(current_user.id)
    return [CollectionRead.model_validate(c) for c in collections]


@router.post(
    "/{collection_id}/notes",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add a note to a collection",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Collection or note owned by another user"},
        404: {"description": "Collection or note not found"},
    },
)
async def add_note_to_collection(
    collection_id: int,
    data: NoteAddBody,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """POST /collections/{id}/notes — add a note the user owns to a collection they own."""
    await _make_service(session).add_note(collection_id, data.note_id, current_user)


@router.delete(
    "/{collection_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a note from a collection",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Collection owned by another user"},
        404: {"description": "Collection or note not found in collection"},
    },
)
async def remove_note_from_collection(
    collection_id: int,
    note_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """DELETE /collections/{id}/notes/{note_id} — remove a note from a collection."""
    await _make_service(session).remove_note(collection_id, note_id, current_user)


@router.get(
    "/{collection_id}/notes",
    response_model=NoteListResponse,
    summary="List a collection's notes",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Collection owned by another user"},
        404: {"description": "Collection not found"},
    },
)
async def list_collection_notes(
    collection_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    """GET /collections/{id}/notes — paginated NoteListResponse for the collection."""
    return await _make_service(session).list_notes(
        collection_id, page, size, current_user
    )
