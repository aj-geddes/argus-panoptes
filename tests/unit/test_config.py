"""Tests for ConfigManager with hot-reload functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class TestConfigManager:
    """Test suite for the ConfigManager class."""

    def test_load_config_from_yaml(self, config_file: Path) -> None:
        """ConfigManager should load a YAML config file."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        assert manager.get("server.host") == "0.0.0.0"
        assert manager.get("server.port") == 8000

    def test_dot_notation_access(self, config_file: Path) -> None:
        """ConfigManager.get() should support dot-notation for nested keys."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        assert manager.get("database.url") == "sqlite+aiosqlite:///:memory:"
        assert manager.get("database.pool_size") == 5

    def test_default_value_for_missing_key(self, config_file: Path) -> None:
        """ConfigManager.get() should return default for missing keys."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        assert manager.get("nonexistent.key") is None
        assert manager.get("nonexistent.key", "fallback") == "fallback"

    def test_nested_config_access(self, config_file: Path) -> None:
        """ConfigManager should access deeply nested values."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        cost = manager.get("cost_model.providers.openai.gpt-4o.input")
        assert cost == 2.50

    def test_hot_reload_detects_change(
        self, config_file: Path, sample_config: dict[str, Any]
    ) -> None:
        """ConfigManager should detect and reload changed config files."""
        from argus.core.config import ConfigManager

        reload_called = []

        def on_change(new_config: dict[str, Any]) -> None:
            reload_called.append(new_config)

        manager = ConfigManager(str(config_file), on_change=on_change)
        # on_change is called during initial load
        initial_count = len(reload_called)

        # Modify the config file
        sample_config["server"]["port"] = 9999
        config_file.write_text(yaml.dump(sample_config))

        # Trigger reload manually (hot-reload uses watchdog in production)
        changed = manager._load()
        assert changed is True
        assert manager.get("server.port") == 9999
        assert len(reload_called) > initial_count

    def test_no_reload_when_unchanged(self, config_file: Path) -> None:
        """ConfigManager should not reload if file content hasn't changed."""
        from argus.core.config import ConfigManager

        reload_count = []

        def on_change(new_config: dict[str, Any]) -> None:
            reload_count.append(1)

        manager = ConfigManager(str(config_file), on_change=on_change)
        initial_count = len(reload_count)

        # Call _load again without changing the file
        changed = manager._load()
        assert changed is False
        assert len(reload_count) == initial_count

    def test_config_hash_changes_on_modification(
        self, config_file: Path, sample_config: dict[str, Any]
    ) -> None:
        """Internal hash should change when config content changes."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        original_hash = manager._hash

        sample_config["server"]["log_level"] = "WARNING"
        config_file.write_text(yaml.dump(sample_config))
        manager._load()

        assert manager._hash != original_hash

    def test_start_and_stop_watching(self, config_file: Path) -> None:
        """ConfigManager should start and stop the file watcher without errors."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        manager.start_watching()
        assert manager._observer is not None
        manager.stop_watching()

    def test_get_entire_section(self, config_file: Path) -> None:
        """ConfigManager.get() with a section key should return the full dict."""
        from argus.core.config import ConfigManager

        manager = ConfigManager(str(config_file))
        server = manager.get("server")
        assert isinstance(server, dict)
        assert "host" in server
        assert "port" in server
