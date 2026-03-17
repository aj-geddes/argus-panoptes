"""FastAPI application entry point for Argus Panoptes."""

from __future__ import annotations

import contextlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from argus import __version__
from argus.core.config import ConfigManager
from argus.core.database import create_tables, dispose_engine, init_engine
from argus.routes.api.agents import router as agents_router
from argus.routes.api.ingest import router as ingest_router
from argus.routes.api.metrics import router as metrics_router
from argus.routes.api.sse import router as sse_router
from argus.routes.api.traces import router as traces_api_router
from argus.routes.views.dashboard import router as dashboard_router
from argus.routes.views.traces import router as traces_view_router
from argus.services.ingestion import init_cost_calculator

logger = logging.getLogger(__name__)

# Module-level config reference
_config: ConfigManager | None = None


def on_config_change(new_config: dict[str, Any]) -> None:
    """Called when config.yaml changes on disk."""
    # Re-initialize cost calculator with new pricing
    cost_model = new_config.get("cost_model", {})
    if cost_model:
        init_cost_calculator(cost_model)
    logger.info("Configuration reloaded successfully")


def create_app(config_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    global _config

    # Resolve config path
    if config_path is None:
        config_path = os.environ.get("ARGUS_CONFIG_PATH", "config/argus.yaml")

    _config = ConfigManager(config_path, on_change=on_config_change)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        """Application lifespan: startup and shutdown."""
        # Startup
        db_url = _config.get("database.url", "sqlite+aiosqlite:///./argus.db")
        pool_size = _config.get("database.pool_size", 5)
        init_engine(db_url, pool_size)
        await create_tables()
        _config.start_watching()
        logger.info("Argus Panoptes v%s started", __version__)
        yield
        # Shutdown
        _config.stop_watching()
        await dispose_engine()
        logger.info("Argus Panoptes shutdown complete")

    app = FastAPI(
        title="Argus Panoptes",
        description="The all-seeing eye for your AI agents.",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "ok",
            "version": __version__,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # Mount static files (may not exist in test environment)
    with contextlib.suppress(Exception):
        app.mount("/static", StaticFiles(directory="static"), name="static")

    # Include routers
    app.include_router(ingest_router)
    app.include_router(agents_router)
    app.include_router(metrics_router)
    app.include_router(traces_api_router)
    app.include_router(sse_router)
    app.include_router(traces_view_router)
    app.include_router(dashboard_router)

    return app


# Default app instance for uvicorn
app = create_app()
