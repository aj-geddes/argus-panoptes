"""Pydantic schemas for config validation."""

from __future__ import annotations

from pydantic import BaseModel


class ServerConfig(BaseModel):
    """Server configuration section."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    log_level: str = "INFO"


class DatabaseConfig(BaseModel):
    """Database configuration section."""

    url: str = "sqlite+aiosqlite:///./argus.db"
    pool_size: int = 10


class IngestionConfig(BaseModel):
    """Ingestion layer configuration."""

    otlp_enabled: bool = True
    otlp_port: int = 4318
    rest_enabled: bool = True
    max_batch_size: int = 1000
    flush_interval_seconds: int = 5


class ArgusConfig(BaseModel):
    """Top-level Argus configuration."""

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    ingestion: IngestionConfig = IngestionConfig()
