"""SQLAlchemy async database engine and session management.

Supports both SQLite (development) and PostgreSQL (production) backends.
The backend is auto-detected from the database URL.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# Module-level engine and session factory (initialized at app startup)
_engine = None
_session_factory = None

# Default SQLite URL for development
_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./argus.db"


def resolve_database_url(config_url: str | None) -> str:
    """Resolve the database URL from config, env var, or default.

    Priority:
        1. config_url (from argus.yaml database.url)
        2. DATABASE_URL environment variable
        3. Default SQLite URL
    """
    if config_url:
        return config_url
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    return _DEFAULT_DATABASE_URL


def _build_engine_kwargs(database_url: str, pool_size: int = 5) -> dict[str, Any]:
    """Build engine kwargs based on database backend.

    SQLite uses check_same_thread=False and no pool configuration.
    PostgreSQL uses pool_size, max_overflow, and pool_pre_ping.
    """
    kwargs: dict[str, Any] = {"echo": False}

    if database_url.startswith("sqlite"):
        # SQLite-specific settings
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL (or other async-capable databases)
        kwargs["pool_size"] = pool_size
        kwargs["max_overflow"] = pool_size  # Allow burst connections
        kwargs["pool_pre_ping"] = True  # Check connections before use
        kwargs["pool_recycle"] = 3600  # Recycle connections after 1 hour

    return kwargs


def init_engine(database_url: str, pool_size: int = 5) -> None:
    """Initialize the async database engine.

    Automatically configures engine settings based on the database URL:
    - SQLite: check_same_thread=False, no pooling config
    - PostgreSQL: pool_size, max_overflow, pool_pre_ping
    """
    global _engine, _session_factory

    kwargs = _build_engine_kwargs(database_url, pool_size)

    _engine = create_async_engine(database_url, **kwargs)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Log without credentials
    safe_url = database_url.split("@")[-1] if "@" in database_url else database_url
    backend = "PostgreSQL" if "postgresql" in database_url else "SQLite"
    logger.info("Database engine initialized (%s): %s", backend, safe_url)


async def create_tables() -> None:
    """Create all tables defined in SQLModel metadata."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")

    # Import all models so they register with SQLModel.metadata
    import argus.models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables created")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session (for FastAPI dependency injection)."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    async with _session_factory() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the engine (for clean shutdown)."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed")
