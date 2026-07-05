from fastapi import APIRouter
from ollama import AsyncClient

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint — smoke test for 'the service is reachable'.

    Also probes Ollama reachability with a short timeout so a slow/absent
    Ollama never hangs the health check. Overall status stays "ok" even when
    Ollama is down (D-07 degraded-but-200: local AI is optional, core app
    unaffected).
    """
    ollama_status = "ok"
    try:
        client = AsyncClient(host=settings.ollama_base_url, timeout=2.0)
        await client.list()
    except Exception:
        ollama_status = "unreachable"
    return {"status": "ok", "ollama": ollama_status}
