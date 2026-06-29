"""Full-text search router.

GET /search/?q= — user-scoped FULLTEXT BOOLEAN MODE keyword search.
Returns the canonical NoteListResponse pagination envelope.

Registered in app/main.py with prefix="/search".
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.notes.schemas import NoteListResponse
from app.search.repository import SearchRepository
from app.search.service import SearchService

router = APIRouter(tags=["search"])


@router.get("/", response_model=NoteListResponse)
async def search_notes(
    q: str = Query(..., min_length=1, description="BOOLEAN MODE search query"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    """Search notes by keyword using MySQL FULLTEXT BOOLEAN MODE.

    - Supports 2-character tokens (e.g., 'AI', 'Go') — requires innodb_ft_min_token_size=2.
    - BOOLEAN MODE operators: `+required -excluded word*` (wildcard suffix).
    - Malformed operator sequences (@@, ++, +-) are sanitized — never return 500.
    - Results are scoped to the authenticated user (T-04-iso).
    - Sort order: MySQL FULLTEXT relevance score (highest-scoring first, implicit).
    """
    svc = SearchService(SearchRepository(session))
    return await svc.search(q=q, page=page, size=size, user_id=current_user.id)
