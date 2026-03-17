"""Config API routes — read/write config, validation, audit log."""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from argus.schemas.config import validate_config_yaml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])

# Module-level config path reference (set during app init)
_config_path: Path | None = None

# Audit log (in-memory for now; could be persisted to DB in future)
_audit_log: deque[dict[str, Any]] = deque(maxlen=1000)


class ConfigUpdateRequest(BaseModel):
    """Request body for config update."""

    yaml_content: str


class ConfigValidateRequest(BaseModel):
    """Request body for config validation."""

    yaml_content: str


def set_config_path(path: str) -> None:
    """Set the config file path (called during app initialization)."""
    global _config_path
    _config_path = Path(path).resolve()


def get_audit_log() -> list[dict[str, Any]]:
    """Get the audit log entries."""
    return list(_audit_log)


def _add_audit_entry(action: str, details: str = "") -> None:
    """Add an entry to the config audit log."""
    entry = {
        "action": action,
        "timestamp": datetime.now(UTC).isoformat(),
        "details": details,
    }
    _audit_log.append(entry)
    # maxlen=1000 on the deque handles bounding automatically


@router.get("")
async def get_config() -> dict[str, Any]:
    """Get the current config as a JSON dict."""
    if _config_path is None or not _config_path.exists():
        raise HTTPException(status_code=500, detail="Config file path not configured")

    content = _config_path.read_text()
    data = yaml.safe_load(content) or {}
    return {"config": data}


@router.get("/yaml")
async def get_config_yaml() -> dict[str, str]:
    """Get the current config as raw YAML text."""
    if _config_path is None or not _config_path.exists():
        raise HTTPException(status_code=500, detail="Config file path not configured")

    content = _config_path.read_text()
    return {"yaml": content}


@router.post("/validate")
async def validate_config(request: ConfigValidateRequest) -> dict[str, Any]:
    """Validate a YAML config string without applying it."""
    is_valid, errors = validate_config_yaml(request.yaml_content)
    return {
        "valid": is_valid,
        "errors": errors,
    }


@router.post("")
async def update_config(request: ConfigUpdateRequest) -> dict[str, Any]:
    """Update the config file with new YAML content.

    Validates before applying. Returns error if validation fails.
    """
    if _config_path is None:
        raise HTTPException(status_code=500, detail="Config file path not configured")

    # Validate first
    is_valid, errors = validate_config_yaml(request.yaml_content)
    if not is_valid:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Write the new config
    _config_path.write_text(request.yaml_content)
    _add_audit_entry("config_updated", "Config updated via API")
    logger.info("Config updated via API")

    return {"status": "applied", "message": "Configuration updated successfully"}


@router.get("/audit")
async def get_audit() -> dict[str, Any]:
    """Get the config change audit log."""
    return {
        "entries": sorted(_audit_log, key=lambda e: e["timestamp"], reverse=True),
        "total": len(_audit_log),
    }
