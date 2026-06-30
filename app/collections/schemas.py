"""Pydantic v2 schemas for the Collection domain.

Two schemas:
  - CollectionCreate  — request body for POST /collections/
  - CollectionRead    — response body; serialises ORM instance via from_attributes=True

Note: GET /collections/{id}/notes returns NoteListResponse from app.notes.schemas.
Do NOT duplicate that schema — import and reuse it directly.
"""

from pydantic import BaseModel, ConfigDict, Field


class CollectionCreate(BaseModel):
    """Request body for creating a collection."""

    name: str = Field(min_length=1, max_length=255)


class CollectionRead(BaseModel):
    """Response schema for a single collection."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int


class NoteAddBody(BaseModel):
    """Request body for POST /collections/{id}/notes."""

    note_id: int
