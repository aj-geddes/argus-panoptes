"""SQLAlchemy async database engine and session management."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# Module-level engine and session factory (initialized at app startup)
_engine = None
_session_factory = None


def init_engine(database_url: str, pool_size: int = 5) -> None:
    """Initialize the async database engine."""
    global _engine, _session_factory

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("Database engine initialized: %s", database_url.split("@")[-1])


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
