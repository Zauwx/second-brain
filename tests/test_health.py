import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_200_and_ok_body() -> None:
    """GET /health must return 200 with status "ok" and an "ollama" key.

    Uses ASGITransport to test in-process — no live server required.
    """
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "ollama" in response.json()


@pytest.mark.asyncio
async def test_health_reports_ollama_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /health stays 200 and reports ollama="unreachable" when Ollama is down (D-07).

    House style: hand-rolled monkeypatch stub, not unittest.mock (D-10).
    """

    class _StubClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def list(self) -> None:
            raise ConnectionError("mock: ollama unreachable")

    monkeypatch.setattr("app.api.health.AsyncClient", _StubClient)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["ollama"] == "unreachable"
