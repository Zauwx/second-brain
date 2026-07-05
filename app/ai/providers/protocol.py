"""LLMProvider protocol — the minimal contract every AI backend implements.

D-06: build a thin provider abstraction now. This phase ships a single
concrete implementation (OllamaProvider, local LLM). Phase 6 adds an
AnthropicProvider (cloud LLM) implementing this exact same Protocol — no
changes to AIService or the router are required when that lands.

Deliberately one method: prompt construction (summarize vs. tag-suggest vs.,
later, RAG-answer) is an AIService (business logic) concern, not a provider
concern. This keeps the Protocol trivially satisfiable by a fake in tests.
"""

from typing import Protocol


class LLMProvider(Protocol):
    """Minimal contract for any local or cloud LLM backend (D-06)."""

    async def complete(self, prompt: str, *, json_mode: bool = False) -> str: ...
