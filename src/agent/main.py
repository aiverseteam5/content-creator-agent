"""FastAPI application with lifespan management (startup/shutdown)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent import __version__
from agent.core.config import get_settings
from agent.core.database import close_db, get_engine, init_db
from agent.core.logging import get_logger, setup_logging
from agent.core.schemas import HealthResponse
from agent.slack_bot import start_slack_bot

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown lifecycle."""
    # --- Startup ---
    setup_logging()
    logger.info("starting_app", version=__version__)

    await init_db()
    logger.info("database_initialized")

    try:
        start_slack_bot()
    except Exception as exc:
        logger.warning("slack_bot_start_failed", error=str(exc))

    yield

    # --- Shutdown ---
    logger.info("shutting_down")
    await close_db()
    logger.info("database_closed")


app = FastAPI(
    title="Content Creator AI Agent",
    description="AI-powered content creation agent for LinkedIn and X/Twitter",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware (useful for any future web dashboard in Phase 2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Health check endpoint — verifies app, database, and Redis status."""
    settings = get_settings()

    # Check database connection
    db_status = "unknown"
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"
        logger.error("health_check_db_error", error=str(e))

    # Check Redis connection
    redis_status = "unknown"
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        redis_status = "connected"
        await redis_client.aclose()
    except Exception as e:
        redis_status = f"error: {str(e)[:100]}"
        logger.error("health_check_redis_error", error=str(e))

    return HealthResponse(
        status="healthy" if db_status == "connected" and redis_status == "connected" else "degraded",
        version=__version__,
        environment=settings.environment,
        database=db_status,
        redis=redis_status,
    )


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": "Content Creator AI Agent",
        "version": __version__,
        "docs": "/docs",
    }
