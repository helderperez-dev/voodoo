"""Bounded single-process HTTP rate limiting."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from voodoo.config import config

__all__ = ["RateLimiter", "RateLimitMiddleware", "rate_limiter"]


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self, *, max_clients: int = 10_000) -> None:
        if max_clients <= 0:
            raise ValueError("max_clients must be positive")
        # Maps client_id -> list of timestamps
        self.history: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._max_clients = max_clients

    async def is_allowed(
        self, client_id: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Checks if client is allowed to make a request.
        Returns: (is_allowed, remaining_requests, reset_after_seconds)
        """
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            if client_id not in self.history and len(self.history) >= self._max_clients:
                stale_clients = [
                    key
                    for key, values in self.history.items()
                    if not values or values[-1] <= window_start
                ]
                for key in stale_clients:
                    self.history.pop(key, None)
                if len(self.history) >= self._max_clients:
                    oldest_client = min(
                        self.history,
                        key=lambda key: self.history[key][-1],
                    )
                    self.history.pop(oldest_client, None)
            timestamps = self.history[client_id]
            # Filter out timestamps outside window
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= max_requests:
                # Calculate when the oldest request in the window will drop off
                oldest = valid_timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                self.history[client_id] = valid_timestamps
                return False, 0, retry_after

            valid_timestamps.append(now)
            self.history[client_id] = valid_timestamps
            remaining = max(0, max_requests - len(valid_timestamps))
            return True, remaining, 0

    def reset(self) -> None:
        """Clears all rate limit records."""
        self.history.clear()


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware protecting against abuse and brute-force attacks.
    """

    def __init__(self, app: Any, *, config_override: Any = None) -> None:
        super().__init__(app)
        self._config = config_override or config

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = self._config.security

        if not sec_cfg.rate_limit_enabled:
            return await call_next(request)

        # Unvalidated credential strings must not create attacker-controlled
        # buckets. Only authenticated identity may replace the client address.
        client_ip = request.client.host if request.client else "127.0.0.1"
        client_id = f"ip:{client_ip}"
        user = getattr(request.state, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            identity = str(getattr(user, "id", None) or getattr(user, "username", ""))
            if identity:
                digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
                client_id = f"principal:{digest}"

        allowed, remaining, retry_after = await rate_limiter.is_allowed(
            client_id=client_id,
            max_requests=sec_cfg.rate_limit_requests,
            window_seconds=sec_cfg.rate_limit_window,
        )

        if not allowed:
            resp = JSONResponse(
                {
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "code": 429,
                    "retry_after": retry_after,
                },
                status_code=429,
            )
            resp.headers["Retry-After"] = str(retry_after)
            resp.headers["X-RateLimit-Limit"] = str(sec_cfg.rate_limit_requests)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(retry_after)
            return resp

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(sec_cfg.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
