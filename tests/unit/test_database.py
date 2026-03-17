"""Tests for database engine and session management."""

from __future__ import annotations

import pytest


class TestDatabaseModule:
    """Test suite for core database functionality."""

    def test_init_engine_sqlite(self) -> None:
        """init_engine should create an engine for SQLite."""
        from argus.core import database as db

        # Reset module state
        db._engine = None
        db._session_factory = None

        db.init_engine("sqlite+aiosqlite:///:memory:", pool_size=5)
        assert db._engine is not None
        assert db._session_factory is not None

        # Cleanup
        db._engine = None
        db._session_factory = None

    @pytest.mark.asyncio
    async def test_create_tables_without_engine_raises(self) -> None:
        """create_tables should raise RuntimeError if engine is not initialized."""
        from argus.core import database as db

        saved_engine = db._engine
        db._engine = None
        with pytest.raises(RuntimeError, match="not initialized"):
            await db.create_tables()
        db._engine = saved_engine

    @pytest.mark.asyncio
    async def test_get_session_without_engine_raises(self) -> None:
        """get_session should raise RuntimeError if engine is not initialized."""
        from argus.core import database as db

        saved_factory = db._session_factory
        db._session_factory = None
        with pytest.raises(RuntimeError, match="not initialized"):
            async for _ in db.get_session():
                pass
        db._session_factory = saved_factory

    @pytest.mark.asyncio
    async def test_dispose_engine(self) -> None:
        """dispose_engine should clean up engine and session factory."""
        from argus.core import database as db

        db.init_engine("sqlite+aiosqlite:///:memory:")
        assert db._engine is not None
        await db.dispose_engine()
        assert db._engine is None
        assert db._session_factory is None

    @pytest.mark.asyncio
    async def test_dispose_engine_when_none(self) -> None:
        """dispose_engine should be safe to call when engine is None."""
        from argus.core import database as db

        db._engine = None
        db._session_factory = None
        await db.dispose_engine()  # Should not raise

    @pytest.mark.asyncio
    async def test_create_tables_and_get_session(self) -> None:
        """Full round trip: init, create tables, get session, dispose."""
        import argus.models  # noqa: F401
        from argus.core import database as db

        db.init_engine("sqlite+aiosqlite:///:memory:")
        await db.create_tables()

        async for session in db.get_session():
            assert session is not None
            break

        await db.dispose_engine()
