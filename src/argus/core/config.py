"""ConfigManager with file-system hot-reload via watchdog."""

from __future__ import annotations

import hashlib
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigManager:
    """Thread-safe configuration with file-system hot-reload."""

    def __init__(
        self,
        config_path: str,
        on_change: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._path: Path = Path(config_path).resolve()
        self._config: dict[str, Any] = {}
        self._hash: str = ""
        self._lock: threading.RLock = threading.RLock()
        self._on_change: Callable[[dict[str, Any]], None] | None = on_change
        self._observer: Any = None
        self._load()

    def _load(self) -> bool:
        """Load config from disk. Returns True if content changed."""
        content = self._path.read_text()
        new_hash = hashlib.sha256(content.encode()).hexdigest()
        if new_hash == self._hash:
            return False
        with self._lock:
            self._config = yaml.safe_load(content) or {}
            self._hash = new_hash
        logger.info("Config loaded from %s (hash: %s...)", self._path, new_hash[:8])
        if self._on_change:
            self._on_change(self._config)
        return True

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-notation access: config.get('alerts.rules')."""
        with self._lock:
            value: Any = self._config
            for part in key.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return default
            return value if value is not None else default

    def start_watching(self) -> None:
        """Start the file-system watcher for hot-reload."""
        handler = _ConfigFileHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._path.parent), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Config watcher started for %s", self._path)

    def stop_watching(self) -> None:
        """Stop the file-system watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("Config watcher stopped")


class _ConfigFileHandler(FileSystemEventHandler):
    """Watchdog handler that triggers config reload on file modification."""

    def __init__(self, manager: ConfigManager) -> None:
        self._manager = manager
        self._debounce_timer: threading.Timer | None = None

    def on_modified(self, event: Any) -> None:
        """Handle file modification events with debouncing."""
        if Path(event.src_path).resolve() != self._manager._path:
            return
        # Debounce: editors often trigger multiple save events
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(0.5, self._manager._load)
        self._debounce_timer.start()
