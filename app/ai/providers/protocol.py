"""LLMProvider protocol — the minimal contract every AI backend implements.

D-06: build a thin provider abstraction now. This phase ships a single
concrete implementation (OllamaProvider, local LLM). Phase 6 adds an
AnthropicProvider (cloud LLM) implementing this exact same Protocol — no
changes to AIService or the router are required when that lands.

Deliberately one method: prompt construction (summarize vs. tag-suggest vs.,
later, RAG-answer) is an AIService (business logic) concern, not a provider
concern. This keeps the Protocol trivially satisfiable by a fake in tests.

`format` is a pass-through transport hint, not a provider-owned concept — the
CALLER (AIService) owns any schema it wants enforced; the transport layer
must not know about tagging or any other domain shape. A future
AnthropicProvider maps this same value onto tool-use / JSON mode.
"""

from typing import Protocol


class LLMProvider(Protocol):
    """Minimal contract for any local or cloud LLM backend (D-06)."""

    async def complete(self, prompt: str, *, format: str | dict = "") -> str: ...
