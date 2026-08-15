import asyncio
import pytest
import time
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, PlainTextResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.testclient import TestClient

from voodoo.security import (
    SecurityHeadersMiddleware,
    CORSMiddleware,
    CSRFMiddleware,
    RateLimitMiddleware,
    RateLimiter,
    rate_limiter,
    generate_csrf_token,
    set_csrf_cookie,
    validate_password_strength,
)
from voodoo.config import config


def test_password_strength_validator():
    # Too short
    ok, err = validate_password_strength("Short1!")
    assert ok is False
    assert "8 characters" in err

    # No numbers or symbols
    ok, err = validate_password_strength("AllLettersPassword")
    assert ok is False
    assert "number or symbol" in err

    # Valid
    ok, err = validate_password_strength("SuperSecret99!")
    assert ok is True
    assert err == ""


def test_security_headers_middleware():
    async def hello(request: Request):
        return PlainTextResponse("Hello Security")

    app = Starlette(
        routes=[Route("/hello", hello, methods=["GET"])],
        middleware=[Middleware(SecurityHeadersMiddleware)],
    )
    client = TestClient(app)

    response = client.get("/hello")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    assert "default-src" in response.headers["Content-Security-Policy"]


def test_cors_middleware():
    async def api_endpoint(request: Request):
        return JSONResponse({"data": "ok"})

    app = Starlette(
        routes=[Route("/api/data", api_endpoint, methods=["GET", "POST"])],
        middleware=[Middleware(CORSMiddleware)],
    )
    client = TestClient(app)

    # 1. Preflight OPTIONS request
    preflight = client.options(
        "/api/data",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert preflight.status_code == 204
    assert preflight.headers.get("Access-Control-Allow-Origin") == "https://example.com"
    assert "POST" in preflight.headers.get(
        "Access-Control-Allow-Methods", ""
    ) or "*" in preflight.headers.get("Access-Control-Allow-Methods", "")
    assert preflight.headers.get("Access-Control-Allow-Credentials") == "true"

    # 2. Standard GET request with Origin
    res = client.get("/api/data", headers={"Origin": "https://example.com"})
    assert res.status_code == 200
    assert res.headers.get("Access-Control-Allow-Origin") == "https://example.com"


def test_csrf_middleware():
    # Enable CSRF for testing
    config.security.csrf_enabled = True

    async def get_page(request: Request):
        return PlainTextResponse("Page")

    async def post_action(request: Request):
        return JSONResponse({"saved": True})

    app = Starlette(
        routes=[
            Route("/page", get_page, methods=["GET"]),
            Route("/action", post_action, methods=["POST"]),
        ],
        middleware=[Middleware(CSRFMiddleware)],
    )
    client = TestClient(app)

    try:
        # 1. GET requests automatically set CSRF cookie
        r_get = client.get("/page")
        assert r_get.status_code == 200
        csrf_cookie = r_get.cookies.get(config.security.csrf_cookie_name)
        assert csrf_cookie is not None

        # 2. Mutating POST without CSRF header should fail (403)
        r_post_fail = client.post(
            "/action", cookies={config.security.csrf_cookie_name: csrf_cookie}
        )
        assert r_post_fail.status_code == 403

        # 3. Mutating POST with matching CSRF header and cookie should succeed
        r_post_ok = client.post(
            "/action",
            cookies={config.security.csrf_cookie_name: csrf_cookie},
            headers={config.security.csrf_header_name: csrf_cookie},
        )
        assert r_post_ok.status_code == 200
        assert r_post_ok.json()["saved"] is True

        # 4. Mutating POST with API Key is exempt from CSRF
        r_post_api = client.post("/action", headers={"X-API-Key": "vd_live_test_key"})
        assert r_post_api.status_code == 200
    finally:
        config.security.csrf_enabled = False


def test_rate_limiting_middleware():
    rate_limiter.reset()

    # Configure tight limit for testing: 3 requests per 60 seconds
    orig_reqs = config.security.rate_limit_requests
    orig_window = config.security.rate_limit_window
    config.security.rate_limit_requests = 3
    config.security.rate_limit_window = 60
    config.security.rate_limit_enabled = True

    async def ping(request: Request):
        return PlainTextResponse("pong")

    app = Starlette(
        routes=[Route("/ping", ping, methods=["GET"])],
        middleware=[Middleware(RateLimitMiddleware)],
    )
    client = TestClient(app)

    try:
        # Request 1: OK
        r1 = client.get("/ping")
        assert r1.status_code == 200
        assert r1.headers.get("X-RateLimit-Remaining") == "2"

        # Request 2: OK
        r2 = client.get("/ping")
        assert r2.status_code == 200
        assert r2.headers.get("X-RateLimit-Remaining") == "1"

        # Request 3: OK
        r3 = client.get("/ping")
        assert r3.status_code == 200
        assert r3.headers.get("X-RateLimit-Remaining") == "0"

        # Request 4: Blocked with 429
        r4 = client.get("/ping")
        assert r4.status_code == 429
        assert r4.json()["error"] == "Too Many Requests"
        assert "Retry-After" in r4.headers
    finally:
        # Restore configuration
        config.security.rate_limit_requests = orig_reqs
        config.security.rate_limit_window = orig_window
        rate_limiter.reset()
