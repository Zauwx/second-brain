"""Shared FastAPI dependency providers.

These functions are injected into route handlers via `Depends()`.
Centralising them here avoids importing from multiple modules and makes
dependency overrides in tests cleaner (one place to patch).

Usage:
    from fastapi import Depends
    from app.core.dependencies import get_db, get_note_service, get_current_user

    @router.get("/notes")
    async def list_notes(svc: NoteService = Depends(get_note_service)):
        ...

    @router.get("/protected")
    async def protected_route(user: User = Depends(get_current_user)):
        ...
"""

from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.protocol import LLMProvider
from app.auth.models import User
from app.auth.repository import AuthRepository
from app.collections.repository import CollectionRepository
from app.collections.service import CollectionService
from app.core.config import settings
from app.database import AsyncSessionLocal
from app.notes.repository import NoteRepository
from app.notes.service import NoteService
from app.search.repository import SearchRepository
from app.search.service import SearchService
from app.tags.repository import TagRepository
from app.tags.service import TagService

# ---------------------------------------------------------------------------
# Bearer scheme: auto_error=False is REQUIRED
# With auto_error=True FastAPI raises 403 (not 401) for missing headers.
# We handle None explicitly in get_current_user to guarantee 401 (Pitfall 3,
# RESEARCH.md Pattern 2, T-03-08).
# ---------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; close it cleanly on response completion."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_note_service(
    db: AsyncSession = Depends(get_db),
) -> NoteService:
    """Construct NoteService with its repository for the current request."""
    return NoteService(NoteRepository(db))


async def get_tag_service(
    db: AsyncSession = Depends(get_db),
) -> TagService:
    """Construct TagService with its repositories for the current request."""
    return TagService(TagRepository(db), NoteRepository(db))


async def get_collection_service(
    db: AsyncSession = Depends(get_db),
) -> CollectionService:
    """Construct CollectionService with its repositories for the current request."""
    return CollectionService(CollectionRepository(db), NoteRepository(db))


async def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SearchService:
    """Construct SearchService with its repository for the current request."""
    return SearchService(SearchRepository(db))


def get_llm_provider() -> LLMProvider:
    """Construct the OllamaProvider from settings.

    This is the seam tests override via app.dependency_overrides (D-10) —
    zero real Ollama calls happen in pytest because this function is never
    invoked; a fake LLMProvider is substituted instead.
    """
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_chat_model,
        timeout=settings.ollama_timeout_seconds,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the Bearer access token and return the authenticated User.

    Security properties (RESEARCH.md Pattern 2, T-03-08, T-03-09, T-03-12):
      - auto_error=False → missing/malformed Authorization header → 401 (not 403)
      - jwt.decode enforces exp (T-03-09) → ExpiredSignatureError → 401
      - sub only (T-03-13) — no mutable email/role claims in payload (Pitfall 4)
      - DB lookup by sub at every request (T-03-12) → stale token after user deletion → 401

    Raises:
        HTTPException 401: For any of: missing credentials, invalid signature,
            expired token, missing sub claim, or user not found in DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Guard: missing or empty Authorization header (Pitfall 3 — auto_error=False gives us None)
    if credentials is None:
        raise credentials_exception

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except (ExpiredSignatureError, InvalidTokenError) as exc:
        # Covers: expired tokens, bad signature, malformed JWT, wrong algorithm
        raise credentials_exception from exc

    # Extract sub — RESEARCH.md Pattern 2; only sub+exp are in access token (D-01/T-03-13)
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    # A validly-signed token whose sub is non-numeric (email, UUID, "null") must
    # map to 401 — not crash with an unhandled ValueError (500) (CR-02).
    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError) as exc:
        raise credentials_exception from exc

    # DB lookup: stale tokens (user deleted, T-03-12) return 401 here
    user = await AuthRepository(db).get_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    return user
