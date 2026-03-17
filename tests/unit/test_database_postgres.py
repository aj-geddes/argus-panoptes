"""Tests for PostgreSQL support in database module."""

from __future__ import annotations

from argus.core.database import _build_engine_kwargs


class TestDatabaseEngineKwargs:
    """Test that engine kwargs are correctly computed for different database backends."""

    def test_sqlite_gets_check_same_thread(self) -> None:
        """SQLite URLs should include check_same_thread=False in connect_args."""
        kwargs = _build_engine_kwargs("sqlite+aiosqlite:///./argus.db", pool_size=5)
        assert kwargs["connect_args"]["check_same_thread"] is False

    def test_sqlite_memory_gets_check_same_thread(self) -> None:
        """SQLite in-memory URLs should include check_same_thread=False."""
        kwargs = _build_engine_kwargs("sqlite+aiosqlite:///:memory:", pool_size=5)
        assert kwargs["connect_args"]["check_same_thread"] is False

    def test_postgresql_no_check_same_thread(self) -> None:
        """PostgreSQL URLs should not include check_same_thread."""
        kwargs = _build_engine_kwargs("postgresql+asyncpg://user:pass@localhost/argus", pool_size=10)
        assert "connect_args" not in kwargs or "check_same_thread" not in kwargs.get("connect_args", {})

    def test_postgresql_gets_pool_size(self) -> None:
        """PostgreSQL URLs should configure pool_size."""
        kwargs = _build_engine_kwargs("postgresql+asyncpg://user:pass@localhost/argus", pool_size=20)
        assert kwargs["pool_size"] == 20

    def test_postgresql_gets_max_overflow(self) -> None:
        """PostgreSQL URLs should configure max_overflow."""
        kwargs = _build_engine_kwargs("postgresql+asyncpg://user:pass@localhost/argus", pool_size=10)
        assert "max_overflow" in kwargs
        assert kwargs["max_overflow"] == 10

    def test_sqlite_no_pool_size(self) -> None:
        """SQLite URLs should not set pool_size (uses StaticPool or NullPool)."""
        kwargs = _build_engine_kwargs("sqlite+aiosqlite:///:memory:", pool_size=10)
        assert "pool_size" not in kwargs

    def test_database_url_from_env(self) -> None:
        """Database URL can be resolved from environment variables."""
        import os

        from argus.core.database import resolve_database_url

        os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@db:5432/argus"
        try:
            url = resolve_database_url(None)
            assert url == "postgresql+asyncpg://user:pass@db:5432/argus"
        finally:
            del os.environ["DATABASE_URL"]

    def test_database_url_config_takes_precedence(self) -> None:
        """Config URL takes precedence over environment variable."""
        import os

        from argus.core.database import resolve_database_url

        os.environ["DATABASE_URL"] = "postgresql+asyncpg://env-url/argus"
        try:
            url = resolve_database_url("sqlite+aiosqlite:///./argus.db")
            assert url == "sqlite+aiosqlite:///./argus.db"
        finally:
            del os.environ["DATABASE_URL"]

    def test_database_url_default_sqlite(self) -> None:
        """When no URL is provided and no env var, default to SQLite."""
        import os

        from argus.core.database import resolve_database_url

        os.environ.pop("DATABASE_URL", None)
        url = resolve_database_url(None)
        assert "sqlite" in url


class TestAlembicEnvPostgres:
    """Test that Alembic env.py properly handles both SQLite and PostgreSQL."""

    def test_env_py_exists(self) -> None:
        """Alembic env.py should exist."""
        from pathlib import Path

        env_path = Path(__file__).parent.parent.parent / "migrations" / "env.py"
        assert env_path.exists()

    def test_env_py_imports_models(self) -> None:
        """Alembic env.py should import all models for metadata registration."""
        from pathlib import Path

        env_content = (Path(__file__).parent.parent.parent / "migrations" / "env.py").read_text()
        assert "import argus.models" in env_content

    def test_env_py_handles_env_var_override(self) -> None:
        """Alembic env.py should support DATABASE_URL env var override."""
        from pathlib import Path

        env_content = (Path(__file__).parent.parent.parent / "migrations" / "env.py").read_text()
        assert "DATABASE_URL" in env_content
