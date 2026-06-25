"""Unit tests for NoteRepository + NoteService ownership scoping (Task 2 — Phase 3).

These tests verify the service/repository layer contracts for per-user isolation:
  - repository.create(data, user_id) persists the user_id
  - repository.list_paginated(..., user_id) returns only that user's notes
  - service.get_or_404_owned raises 404 for missing notes, 403 for wrong owner
  - service.create/update/delete pass current_user correctly

TDD (RED): Written before implementation — all tests fail until Task 2 implementation.
TDD (GREEN): Will pass after repository and service are updated.

Uses the same `session` fixture (testcontainers MySQL + transaction rollback) as other tests.
All tests create real User and Note rows to exercise the real MySQL stack.
"""

import httpx
import pytest
from fastapi import HTTPException

from app.auth.models import User
from app.notes.models import Note
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteUpdate
from app.notes.service import NoteService


# ---------------------------------------------------------------------------
# Helpers — create a bare User row directly in the DB (no HTTP round-trip)
# ---------------------------------------------------------------------------


async def _create_user(session, email: str) -> User:
    """Insert a minimal User row for testing ownership checks."""
    from app.auth.repository import AuthRepository
    from app.auth.schemas import UserCreate

    repo = AuthRepository(session)
    user_data = UserCreate(email=email, password="Test1234!")
    return await repo.create_user(user_data, hashed_password="hashed_placeholder")


# ---------------------------------------------------------------------------
# Repository: create with user_id (D-10)
# ---------------------------------------------------------------------------


async def test_repository_create_persists_user_id(session) -> None:
    """NoteRepository.create(data, user_id) must set note.user_id to the given id."""
    user = await _create_user(session, "repo_create@example.com")
    repo = NoteRepository(session)
    data = NoteCreate(content="repo create test")
    note = await repo.create(data, user_id=user.id)

    assert note.user_id == user.id


# ---------------------------------------------------------------------------
# Repository: list_paginated scoped to user_id (D-09)
# ---------------------------------------------------------------------------


async def test_repository_list_paginated_scopes_to_user(session) -> None:
    """list_paginated(user_id=A) must not return notes owned by user B."""
    user_a = await _create_user(session, "repo_list_a@example.com")
    user_b = await _create_user(session, "repo_list_b@example.com")

    repo = NoteRepository(session)

    # Create one note for each user
    note_a = await repo.create(NoteCreate(content="note for user A"), user_id=user_a.id)
    await repo.create(NoteCreate(content="note for user B"), user_id=user_b.id)

    items_a, total_a = await repo.list_paginated(1, 20, "-created_at", None, user_id=user_a.id)

    assert total_a == 1
    assert len(items_a) == 1
    assert items_a[0].id == note_a.id
    assert items_a[0].user_id == user_a.id


async def test_repository_list_paginated_count_is_scoped(session) -> None:
    """The total count returned by list_paginated reflects only the owner's notes."""
    user_a = await _create_user(session, "repo_count_a@example.com")
    user_b = await _create_user(session, "repo_count_b@example.com")

    repo = NoteRepository(session)
    await repo.create(NoteCreate(content="A note 1"), user_id=user_a.id)
    await repo.create(NoteCreate(content="A note 2"), user_id=user_a.id)
    await repo.create(NoteCreate(content="B note 1"), user_id=user_b.id)

    _, total_a = await repo.list_paginated(1, 20, "-created_at", None, user_id=user_a.id)
    _, total_b = await repo.list_paginated(1, 20, "-created_at", None, user_id=user_b.id)

    assert total_a == 2
    assert total_b == 1


# ---------------------------------------------------------------------------
# Service: get_or_404_owned — 404 vs 403 (D-08)
# ---------------------------------------------------------------------------


async def test_service_get_or_404_owned_returns_note_when_owned(session) -> None:
    """get_or_404_owned(note_id, current_user) returns the note when owner matches."""
    user = await _create_user(session, "svc_owned@example.com")
    repo = NoteRepository(session)
    note = await repo.create(NoteCreate(content="owned note"), user_id=user.id)

    svc = NoteService(repo)
    result = await svc.get_or_404_owned(note.id, user)

    assert result.id == note.id


async def test_service_get_or_404_owned_raises_404_for_missing(session) -> None:
    """get_or_404_owned raises HTTPException 404 when the note doesn't exist."""
    user = await _create_user(session, "svc_missing@example.com")
    repo = NoteRepository(session)
    svc = NoteService(repo)

    with pytest.raises(HTTPException) as exc_info:
        await svc.get_or_404_owned(999999, user)

    assert exc_info.value.status_code == 404


async def test_service_get_or_404_owned_raises_403_for_wrong_owner(session) -> None:
    """get_or_404_owned raises HTTPException 403 when the note exists but owner differs."""
    user_a = await _create_user(session, "svc_403_a@example.com")
    user_b = await _create_user(session, "svc_403_b@example.com")

    repo = NoteRepository(session)
    note = await repo.create(NoteCreate(content="A's note"), user_id=user_a.id)

    svc = NoteService(repo)
    with pytest.raises(HTTPException) as exc_info:
        await svc.get_or_404_owned(note.id, user_b)

    assert exc_info.value.status_code == 403
