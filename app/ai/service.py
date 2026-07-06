"""AIService — business logic for AI-assisted note operations.

Responsibilities:
- Orchestrate the LLMProvider + NoteService + NoteRepository collaborators.
- Reuse NoteService.get_or_404_owned for ownership (404/403) — never
  re-implement that check here (T-05-03, ASVS V4).
- Translate provider failures (connection/timeout/model-not-found) to a
  clean 503 — the only place HTTPException is raised in this module,
  mirroring the existing NoteService/SearchService pattern (D-07).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import ollama
from fastapi import HTTPException, status

from app.ai.prompts import build_summarize_prompt, build_tag_prompt
from app.ai.providers.protocol import LLMProvider
from app.notes.repository import NoteRepository
from app.notes.service import NoteService

if TYPE_CHECKING:
    from app.auth.models import User
    from app.notes.models import Note


def _parse_tag_list(raw: str) -> list[str]:
    """Leniently parse model output into a list of tag strings (D-05).

    Even with json_mode=True, a 3B model can wrap the array in an object
    (`{"tags": [...]}`), add trailing prose, or emit near-JSON. Try direct
    `json.loads`, fall back to regex-extracting the first `[...]` block,
    unwrap a single list-valued dict, coerce/normalize, and default to an
    empty list rather than raising (never eval'd, never trusted as-is).
    """
    data: object
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match is None:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                data = value
                break

    if not isinstance(data, list):
        return []

    return [str(t).strip().lower() for t in data if str(t).strip()]


class AIService:
    """Service layer for AI-assisted note operations (summarize, D-01/D-02/D-03)."""

    def __init__(
        self,
        provider: LLMProvider,
        note_service: NoteService,
        note_repo: NoteRepository,
    ) -> None:
        self._provider = provider
        self._notes = note_service
        self._note_repo = note_repo

    async def summarize(self, note_id: int, current_user: User) -> Note:
        """Generate and persist a 2-3 sentence summary for the caller's own note.

        Sequence:
          1. Resolve ownership via NoteService.get_or_404_owned (404/403).
          2. Build the summarize prompt and call the provider (json_mode=False).
          3. Persist the (stripped) result via NoteRepository.set_summary.
        """
        note = await self._notes.get_or_404_owned(note_id, current_user)
        raw = await self._safe_complete(build_summarize_prompt(note.content))
        return await self._note_repo.set_summary(note, raw.strip())

    async def suggest_tags(self, note_id: int, current_user: User) -> list[str]:
        """Suggest tags for the caller's own note — suggest-only (D-04).

        Never attaches a tag and never persists a summary; the caller is
        expected to attach any of the returned suggestions themselves via
        the existing Phase-4 `POST /notes/{id}/tags` endpoint.

        Sequence:
          1. Resolve ownership via NoteService.get_or_404_owned (404/403).
          2. Build the tag prompt and call the provider (json_mode=True).
          3. Leniently parse the result via _parse_tag_list (never raises).
        """
        note = await self._notes.get_or_404_owned(note_id, current_user)
        raw = await self._safe_complete(build_tag_prompt(note.content), json_mode=True)
        return _parse_tag_list(raw)

    async def _safe_complete(self, prompt: str, *, json_mode: bool = False) -> str:
        """Call the provider, translating connectivity/model failures to 503 (D-07).

        Catches ConnectionError/TimeoutError/OSError (transient connectivity,
        surfaced by tenacity's reraise=True after bounded retries exhaust) and
        ollama.ResponseError (e.g. "model not found" when llama3.2:3b hasn't
        been pulled yet — RESEARCH.md Pitfall 1) so a not-yet-pulled model
        degrades to a clean 503 instead of an unhandled 500.
        """
        try:
            return await self._provider.complete(prompt, json_mode=json_mode)
        except (ConnectionError, TimeoutError, OSError, ollama.ResponseError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local AI service is currently unavailable. Note operations are unaffected.",
            ) from exc
