import asyncio
import hashlib
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from voodoo.config import config


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        # Maps client_id -> list of timestamps
        self.history: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(
        self, client_id: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Checks if client is allowed to make a request.
        Returns: (is_allowed, remaining_requests, reset_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
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

    def reset(self):
        """Clears all rate limit records."""
        self.history.clear()


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware protecting against abuse and brute-force attacks.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = config.security

        if not sec_cfg.rate_limit_enabled:
            return await call_next(request)

        # Determine client identifier: API key, user id, or client IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        api_key = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization", "")

        client_id = f"ip:{client_ip}"
        if api_key:
            client_id = f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        elif auth_header.startswith("Bearer "):
            client_id = f"token:{hashlib.sha256(auth_header.encode()).hexdigest()[:16]}"

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
