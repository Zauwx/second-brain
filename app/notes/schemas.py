"""Pydantic v2 schemas for the Note domain.

Three-schema pattern (FastAPI best practice):
  - NoteCreate  — used for POST /notes/ request body
  - NoteUpdate  — used for PUT /notes/{id} request body (all fields optional)
  - NoteRead    — used for all responses; serialises ORM model via from_attributes=True

The NoteRead schema uses `model_config = ConfigDict(from_attributes=True)` so that
SQLAlchemy ORM instances can be passed directly to `NoteRead.model_validate(orm_obj)`.

Phase note: no `user_id` field here — added in Phase 3 when auth is introduced.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    """Request body for creating a new note."""

    title: str | None = Field(
        default=None,
        max_length=512,
        description="Optional note title (max 512 characters)",
    )
    content: str = Field(
        min_length=1,
        description="Main note content (required)",
    )
    source_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional URL of the original source",
    )


class NoteUpdate(BaseModel):
    """Request body for partially updating a note.

    All fields are optional — only provided fields will be updated.
    """

    title: str | None = Field(
        default=None,
        max_length=512,
        description="New title (set to null to clear)",
    )
    content: str | None = Field(
        default=None,
        min_length=1,
        description="New content",
    )
    source_url: str | None = Field(
        default=None,
        max_length=2048,
        description="New source URL (set to null to clear)",
    )


class NoteRead(BaseModel):
    """Response schema for a single note.

    Uses `from_attributes=True` so SQLAlchemy ORM instances can be
    passed directly without manual dict conversion.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    source_url: str | None
    user_id: int
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    """Pagination envelope for GET /notes/ — {items, total, page, size, pages}."""

    items: list[NoteRead]
    total: int = Field(description="Total number of notes matching the query")
    page: int = Field(description="Current page number (1-indexed)")
    size: int = Field(description="Number of items per page")
    pages: int = Field(description="Total number of pages")


# Deprecated alias — kept for backward compatibility during transition.
PaginatedNotes = NoteListResponse
