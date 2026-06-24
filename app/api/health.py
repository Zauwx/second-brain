from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint — smoke test for 'the service is reachable'."""
    return {"status": "ok"}
