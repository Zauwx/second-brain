"""FastAPI router for AI endpoints.

Endpoints (prefix "/ai", registered in app/main.py):
  POST /ai/summarize — generate + persist a 2-3 sentence summary for a note
  POST /ai/suggest-tags — suggest tags for a note (suggest-only, D-04)

All endpoints require a valid Bearer access token (get_current_user -> 401).
Ownership checks: 403 if note belongs to another user; 404 if note missing
(reused from NoteService.get_or_404_owned via AIService, T-05-03).
Provider failures (Ollama down/erroring) surface as a clean 503, not a
generic 500 (D-07).
"""

from fastapi import APIRouter, Depends, status

from app.ai.schemas import SuggestTagsRequest, SuggestTagsResponse, SummarizeRequest
from app.ai.service import AIService
from app.auth.models import User
from app.core.dependencies import get_ai_service, get_current_user
from app.notes.schemas import NoteRead

router = APIRouter(tags=["ai"])


@router.post(
    "/summarize",
    response_model=NoteRead,
    status_code=status.HTTP_200_OK,
    summary="Generate and persist an AI summary for a note",
    description=(
        "Generates a 2-3 sentence summary of the caller's own note via the "
        "local LLM (llama3.2:3b) and persists it on the note (D-01, D-02, D-03). "
        "The request blocks synchronously until the summary is ready. "
        "Requires auth; 403 if note belongs to another user; 404 if note missing; "
        "503 if the local AI service is unavailable (note CRUD is unaffected)."
    ),
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note is owned by another user"},
        404: {"description": "Note not found"},
        503: {"description": "Local AI service unavailable"},
    },
)
async def summarize(
    data: SummarizeRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> NoteRead:
    """POST /ai/summarize — generate + persist an AI summary (AIL-01, criterion 2)."""
    note = await ai_service.summarize(data.note_id, current_user)
    return NoteRead.model_validate(note)


@router.post(
    "/suggest-tags",
    response_model=SuggestTagsResponse,
    status_code=status.HTTP_200_OK,
    summary="Suggest tags for a note (suggest-only)",
    description=(
        "Suggests 3-5 tags for the caller's own note via the local LLM "
        "(llama3.2:3b), returning a JSON list of tag strings. Suggest-only — "
        "does NOT attach or persist anything (D-04); attach any of the "
        "returned tags yourself via POST /notes/{id}/tags. "
        "Requires auth; 403 if note belongs to another user; 404 if note missing; "
        "503 if the local AI service is unavailable (note CRUD is unaffected)."
    ),
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note is owned by another user"},
        404: {"description": "Note not found"},
        503: {"description": "Local AI service unavailable"},
    },
)
async def suggest_tags(
    data: SuggestTagsRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
) -> SuggestTagsResponse:
    """POST /ai/suggest-tags — suggest (never attach/persist) tags (AIL-02, criterion 3)."""
    tags = await ai_service.suggest_tags(data.note_id, current_user)
    return SuggestTagsResponse(tags=tags)
