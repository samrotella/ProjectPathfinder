"""Authentication and rate limiting.

MVP posture: static API keys via the X-API-Key header, plus a per-key in-process
sliding-window rate limiter. This is deliberately simple and correct for a
single node. The production path (OAuth2 client-credentials / JWT with scopes,
and a Redis-backed limiter that works across nodes) is described in CLAUDE.md.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, status

from app.config import get_settings

settings = get_settings()

# key -> timestamps of recent requests
_hits: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(api_key: str) -> None:
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests
    now = time.monotonic()
    bucket = _hits[api_key]
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
            headers={"Retry-After": str(window)},
        )
    bucket.append(now)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """FastAPI dependency: validate the API key and apply rate limiting."""
    if not x_api_key or x_api_key not in settings.api_key_set:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    _check_rate_limit(x_api_key)
    return x_api_key
