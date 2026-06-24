from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Second Brain",
    description="Self-hosted second brain: save notes, organize with tags, query in natural language",
    version="0.1.0",
)

app.include_router(health_router)
