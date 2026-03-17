"""Config editor view — in-browser YAML config editing with HTMX save."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from argus.routes.api.config import _add_audit_entry
from argus.schemas.config import validate_config_yaml

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")

# Module-level config path reference
_config_path: Path | None = None


def set_config_path(path: str) -> None:
    """Set the config file path for the editor view."""
    global _config_path
    _config_path = Path(path).resolve()


@router.get("/config", response_class=HTMLResponse)
async def config_editor(request: Request) -> Any:
    """Render the config editor page."""
    config_yaml = ""
    if _config_path and _config_path.exists():
        config_yaml = _config_path.read_text()

    return templates.TemplateResponse(
        request=request,
        name="pages/config.html",
        context={
            "config_yaml": config_yaml,
            "status": None,
            "errors": [],
        },
    )


@router.post("/config/update", response_class=HTMLResponse)
async def config_update(
    request: Request,
    config_yaml: str = Form(...),
) -> Any:
    """Handle config save from the editor form.

    Validates, writes to disk, and returns status partial.
    """
    status = None
    errors: list[str] = []

    # Validate
    is_valid, validation_errors = validate_config_yaml(config_yaml)

    if not is_valid:
        status = "error"
        errors = validation_errors
    elif _config_path is not None:
        try:
            _config_path.write_text(config_yaml)
            status = "success"
            _add_audit_entry("config_updated", "Config updated via web editor")
            logger.info("Config updated via web editor")
        except OSError as e:
            status = "error"
            errors = [f"Failed to write config file: {e}"]
    else:
        status = "error"
        errors = ["Config file path not configured"]

    return templates.TemplateResponse(
        request=request,
        name="pages/config.html",
        context={
            "config_yaml": config_yaml,
            "status": status,
            "errors": errors,
        },
    )
