"""Pydantic v2 schemas for the AI domain.

The response for POST /ai/summarize reuses NoteRead (already gains a
`summary` field per D-02) rather than a bespoke schema — this returns the
full persisted note, matching criterion 2's "summary is persisted on the
note" contract without redefining fields already owned by the Notes domain.
"""

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    """Request body for POST /ai/summarize — the caller's own note id."""

    note_id: int
