"""REST ingestion endpoint for OTLP-compatible trace data."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from argus.core.database import get_session
from argus.schemas.otlp import IngestRequest
from argus.services.ingestion import process_ingest_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


@router.post("/traces")
async def ingest_traces(
    request: IngestRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Accept OTLP JSON trace data (GenAI semantic conventions v1.37)."""
    spans_accepted = await process_ingest_request(session, request)
    return {"status": "ok", "spans_accepted": spans_accepted}
