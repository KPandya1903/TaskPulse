"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.router import router as api_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Distributed Task Orchestrator",
    version="0.1.0",
)

app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
