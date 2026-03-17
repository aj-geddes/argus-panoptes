"""API key authentication and rate limiting middleware for Argus."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that bypass authentication
_EXEMPT_PATHS: set[str] = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Path prefixes that bypass authentication
_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/docs/",
)

# Path prefixes subject to rate limiting (ingestion endpoints)
_RATE_LIMITED_PREFIXES: tuple[str, ...] = ("/v1/",)


def is_exempt_path(path: str) -> bool:
    """Check if a path is exempt from authentication."""
    if path in _EXEMPT_PATHS:
        return True
    return path.startswith(_EXEMPT_PREFIXES)


def is_rate_limited_path(path: str) -> bool:
    """Check if a path is subject to rate limiting."""
    return path.startswith(_RATE_LIMITED_PREFIXES)


def validate_api_key(provided_key: str, expected_key: str) -> bool:
    """Validate an API key using constant-time comparison."""
    if not provided_key or not expected_key:
        return False
    # Use hmac.compare_digest for constant-time comparison to prevent timing attacks
    import hmac

    return hmac.compare_digest(provided_key.encode(), expected_key.encode())


class _RateLimitStore:
    """Simple in-memory rate limiting store using sliding window counters."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str, max_requests: int, window_seconds: int) -> bool:
        """Check if a client is within their rate limit."""
        now = time.monotonic()
        cutoff = now - window_seconds

        # Clean old entries
        self._requests[client_ip] = [ts for ts in self._requests[client_ip] if ts > cutoff]

        if len(self._requests[client_ip]) >= max_requests:
            return False

        self._requests[client_ip].append(now)
        return True

    def reset(self) -> None:
        """Reset all rate limit counters (for testing)."""
        self._requests.clear()


# Module-level rate limit store
_rate_limit_store = _RateLimitStore()


def get_rate_limit_store() -> _RateLimitStore:
    """Return the module-level rate limit store."""
    return _rate_limit_store


def setup_security_middleware(
    app: FastAPI,
    security_config: dict[str, Any] | None = None,
) -> None:
    """Set up API key authentication and rate limiting middleware on the app.

    Args:
        app: The FastAPI application instance.
        security_config: Security configuration dict from argus.yaml.
    """
    if security_config is None:
        security_config = {}

    api_key_config = security_config.get("api_key_auth", {})
    rate_limit_config = security_config.get("rate_limiting", {})

    api_key_enabled = api_key_config.get("enabled", False)
    rate_limit_enabled = rate_limit_config.get("enabled", False)

    if not api_key_enabled and not rate_limit_enabled:
        logger.warning(
            "Security middleware: no auth or rate limiting enabled — "
            "all endpoints including config write are unauthenticated. "
            "Set security.api_key_auth.enabled=true in config to secure your instance."
        )
        return

    # Resolve the API key: config value or env var
    api_key = api_key_config.get("key") or os.environ.get("ARGUS_API_KEY", "")
    header_name = api_key_config.get("header_name", "X-API-Key")

    max_requests = rate_limit_config.get("requests_per_window", 100)
    window_seconds = rate_limit_config.get("window_seconds", 60)

    # Reset rate limit store for fresh app initialization
    _rate_limit_store.reset()

    @app.middleware("http")
    async def security_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Combined API key auth + rate limiting middleware."""
        path = request.url.path

        # --- API key auth ---
        if api_key_enabled and not is_exempt_path(path):
            provided = request.headers.get(header_name, "")
            if not validate_api_key(provided, api_key):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )

        # --- Rate limiting ---
        if rate_limit_enabled and is_rate_limited_path(path):
            client_ip = request.client.host if request.client else "unknown"
            if not _rate_limit_store.is_allowed(client_ip, max_requests, window_seconds):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please retry later."},
                    headers={"Retry-After": str(window_seconds)},
                )

        response: Response = await call_next(request)
        return response

    features = []
    if api_key_enabled:
        features.append("API key auth")
    if rate_limit_enabled:
        features.append(f"rate limiting ({max_requests}/{window_seconds}s)")
    logger.info("Security middleware enabled: %s", ", ".join(features))
