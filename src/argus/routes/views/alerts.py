"""Alert dashboard view — renders alert rules and history page."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from argus.routes.api.alerts import get_alert_engine

logger = logging.getLogger(__name__)

router = APIRouter()

templates = Jinja2Templates(directory="src/templates")


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_dashboard(request: Request) -> Any:
    """Render the alert dashboard page with rules and history."""
    engine = get_alert_engine()
    rules = engine.rules
    history = engine.get_history(limit=50)

    return templates.TemplateResponse(
        request=request,
        name="pages/alerts.html",
        context={
            "rules": rules,
            "history": history,
        },
    )
