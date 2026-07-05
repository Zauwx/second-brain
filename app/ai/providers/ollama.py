"""OllamaProvider — LLMProvider implementation backed by a local Ollama server.

Wraps the `ollama` package's AsyncClient with a bounded tenacity retry
(D-08) around the network call only — retries apply to transient
connectivity/timeout failures, never to downstream parsing errors.

This provider raises ONLY plain library exceptions (ConnectionError,
httpx.TimeoutException, httpx.ConnectError, ollama.ResponseError). It never
raises HTTPException — 503 translation is the service layer's job
(AIService._safe_complete, D-07).
"""

import httpx
from ollama import AsyncClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class OllamaProvider:
    """LLMProvider implementation backed by a local Ollama server (D-06)."""

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        # ollama.AsyncClient.__init__(self, host=None, **kwargs) forwards extra
        # kwargs to the underlying httpx.AsyncClient — `timeout` is a standard
        # httpx.AsyncClient kwarg (RESEARCH.md Pattern 2, Assumption A3).
        self._client = AsyncClient(host=base_url, timeout=timeout)
        self._model = model

    @retry(
        retry=retry_if_exception_type((ConnectionError, httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        response = await self._client.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            format="json" if json_mode else "",
        )
        return response.message.content
