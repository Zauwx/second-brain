"""Pydantic v2 schemas for the Tag domain.

Three-schema pattern (FastAPI best practice):
  - TagCreate  — request body for attaching a tag to a note (just the name)
  - TagRead    — response schema; serialises Tag ORM via from_attributes=True

No TagUpdate (tag rename is deferred, D-03) and no TagListResponse
(GET /tags returns a plain list[TagRead], not paginated).
"""

from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    """Request body for tagging a note — just the name."""

    name: str = Field(min_length=1, max_length=128)


class TagRead(BaseModel):
    """Response schema for a single tag."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int
