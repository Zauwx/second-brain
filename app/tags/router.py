"""FastAPI router for Tag endpoints.

Endpoints (no prefix — this router owns paths on both /tags and /notes/{id}/tags):
  GET    /tags                         — list caller's tags
  POST   /notes/{note_id}/tags         — attach tag to note (find-or-create, normalized)
  DELETE /notes/{note_id}/tags/{name}  — detach tag from note (204)

All endpoints require a valid Bearer access token (get_current_user → 401).
Ownership checks: 403 if note belongs to another user; 404 if note missing.

The router is registered in app/main.py WITHOUT a prefix so it can own paths
on two different path roots (/tags and /notes).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteRead
from app.tags.repository import TagRepository
from app.tags.schemas import TagCreate, TagRead
from app.tags.service import TagService

router = APIRouter(tags=["tags"])


def _make_service(session: AsyncSession) -> TagService:
    """Construct TagService with its repositories for the current request session."""
    return TagService(TagRepository(session), NoteRepository(session))


@router.get(
    "/tags",
    response_model=list[TagRead],
    summary="List caller's tags",
    description=(
        "Returns all tags owned by the authenticated user, ordered by name. "
        "Each user has a private tag namespace — another user's tags are never returned. "
        "Requires a valid Bearer access token — 401 if missing or invalid."
    ),
)
async def list_tags(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TagRead]:
    """GET /tags — list all tags for the authenticated user (T-04-02, T-04-iso)."""
    tags = await _make_service(session).list_tags(user_id=current_user.id)
    return [TagRead.model_validate(t) for t in tags]


@router.post(
    "/notes/{note_id}/tags",
    response_model=NoteRead,
    status_code=status.HTTP_200_OK,
    summary="Attach a tag to a note",
    description=(
        "Attaches a tag to the given note (auto-creates the tag if it does not exist). "
        "Tag names are normalized: trimmed + lowercased — 'Python' and 'python' are the same tag. "
        "Idempotent: posting the same name twice does not create duplicate tags. "
        "Returns the updated NoteRead with the `tags` array populated. "
        "Requires auth; 403 if note belongs to another user; 404 if note missing."
    ),
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note is owned by another user"},
        404: {"description": "Note not found"},
    },
)
async def attach_tag(
    note_id: int,
    data: TagCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """POST /notes/{note_id}/tags — attach a tag to a note (T-04-iso)."""
    note = await _make_service(session).attach_tag(note_id, data.name, current_user)
    return NoteRead.model_validate(note)


@router.delete(
    "/notes/{note_id}/tags/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach a tag from a note",
    description=(
        "Removes the tag with the given name from the note. "
        "The name is normalized (trimmed + lowercased) before lookup. "
        "Returns 204 No Content on success. "
        "Requires auth; 403 if note belongs to another user; 404 if note or tag missing."
    ),
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note is owned by another user"},
        404: {"description": "Note or tag not found"},
    },
)
async def detach_tag(
    note_id: int,
    name: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """DELETE /notes/{note_id}/tags/{name} — detach a tag from a note."""
    await _make_service(session).detach_tag(note_id, name, current_user)
