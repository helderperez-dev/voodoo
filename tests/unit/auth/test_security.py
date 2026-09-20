from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from voodoo.auth import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    set_auth_cookie,
)
from voodoo.config import config
from voodoo.security import (
    CORSMiddleware,
    CSRFMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    generate_csrf_token,
    rate_limiter,
    set_csrf_cookie,
    validate_password_strength,
)


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


# =========================================================================
# Threat Model Coverage (S5-3a)
# =========================================================================


def test_cookie_flags_http_only_and_samesite():
    """Cookie flags: HttpOnly, SameSite, Secure must be enforced."""
    from starlette.responses import Response

    resp = Response("ok")
    set_auth_cookie(resp, "test.token", max_age=3600)
    cookie_header = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header
    # In dev mode, Secure may not be set; verify it's present in production mode
    orig_env = config.env
    orig_secure = config.auth.cookie_secure
    try:
        config.env = "production"
        config.auth.cookie_secure = True
        resp2 = Response("ok")
        set_auth_cookie(resp2, "test.token", max_age=3600)
        assert "Secure" in resp2.headers.get("set-cookie", "")
    finally:
        config.env = orig_env
        config.auth.cookie_secure = orig_secure


def test_jwt_expired_token_rejected():
    """JWT with past expiry must be rejected."""
    from voodoo.auth import ExpiredTokenError

    secret = "threat-model-test-secret"
    token = create_access_token(
        {"sub": 1}, expires_delta_seconds=-100, secret_key=secret
    )
    import pytest

    with pytest.raises(ExpiredTokenError):
        decode_access_token(token, secret_key=secret)


def test_jwt_tampered_signature_rejected():
    """JWT with modified signature must be rejected."""
    secret = "threat-model-test-secret"
    token = create_access_token({"sub": 1}, secret_key=secret)
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.AAAAAAA"
    import pytest

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered, secret_key=secret)


def test_jwt_malformed_exp_claim_rejected():
    """JWT with non-integer exp claim must be rejected (not crash)."""
    secret = "threat-model-test-secret"
    token = create_access_token({"sub": 1, "exp": "not-a-number"}, secret_key=secret)
    import pytest

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret_key=secret)


def test_jwt_nbf_future_claim_rejected():
    """JWT with nbf (not-before) in the future must be rejected."""
    import time

    import pytest

    secret = "threat-model-test-secret"
    future_nbf = int(time.time()) + 3600
    token = create_access_token({"sub": 1, "nbf": future_nbf}, secret_key=secret)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret_key=secret)


def test_csrf_token_generation_uniqueness():
    """CSRF tokens must be unique and cryptographically random."""
    tokens = {generate_csrf_token() for _ in range(100)}
    assert len(tokens) == 100  # All unique


def test_csrf_cookie_not_http_only():
    """CSRF cookie must NOT be HttpOnly (JS needs to read it for header)."""
    from starlette.responses import Response

    resp = Response("ok")
    set_csrf_cookie(resp)
    cookie_header = resp.headers.get("set-cookie", "")
    assert config.security.csrf_cookie_name in cookie_header
    assert "HttpOnly" not in cookie_header


def test_cors_disallowed_origin_not_reflected():
    """CORS must not reflect disallowed origins."""

    async def api_endpoint(request: Request):
        return JSONResponse({"data": "ok"})

    # Restrict to specific origins
    orig_origins = config.security.cors_origins
    try:
        config.security.cors_origins = ["https://allowed.example.com"]
        app = Starlette(
            routes=[Route("/api/data", api_endpoint, methods=["GET"])],
            middleware=[Middleware(CORSMiddleware)],
        )
        client = TestClient(app)

        # Disallowed origin
        res = client.get("/api/data", headers={"Origin": "https://evil.example.com"})
        assert res.headers.get("Access-Control-Allow-Origin") is None
    finally:
        config.security.cors_origins = orig_origins


def test_cors_vary_origin_header():
    """CORS responses with reflected origins must include Vary: Origin."""

    async def api_endpoint(request: Request):
        return JSONResponse({"data": "ok"})

    orig_origins = config.security.cors_origins
    try:
        config.security.cors_origins = ["https://allowed.example.com"]
        app = Starlette(
            routes=[Route("/api/data", api_endpoint, methods=["GET"])],
            middleware=[Middleware(CORSMiddleware)],
        )
        client = TestClient(app)
        res = client.get("/api/data", headers={"Origin": "https://allowed.example.com"})
        assert (
            res.headers.get("Access-Control-Allow-Origin")
            == "https://allowed.example.com"
        )
        assert "Origin" in res.headers.get("Vary", "")
    finally:
        config.security.cors_origins = orig_origins


def test_rate_limit_isolates_clients():
    """Rate limiting should track different clients separately."""
    rate_limiter.reset()
    orig_reqs = config.security.rate_limit_requests
    orig_window = config.security.rate_limit_window
    orig_enabled = config.security.rate_limit_enabled
    try:
        config.security.rate_limit_requests = 2
        config.security.rate_limit_window = 60
        config.security.rate_limit_enabled = True

        async def ping(request: Request):
            return PlainTextResponse("pong")

        app = Starlette(
            routes=[Route("/ping", ping, methods=["GET"])],
            middleware=[Middleware(RateLimitMiddleware)],
        )
        client = TestClient(app)

        # Client A (API key A) exhausts limit
        assert (
            client.get("/ping", headers={"X-API-Key": "key_a_123"}).status_code == 200
        )
        assert (
            client.get("/ping", headers={"X-API-Key": "key_a_123"}).status_code == 200
        )
        assert (
            client.get("/ping", headers={"X-API-Key": "key_a_123"}).status_code == 429
        )

        # Client B (API key B) still allowed
        assert (
            client.get("/ping", headers={"X-API-Key": "key_b_456"}).status_code == 200
        )
    finally:
        config.security.rate_limit_requests = orig_reqs
        config.security.rate_limit_window = orig_window
        config.security.rate_limit_enabled = orig_enabled
        rate_limiter.reset()


def test_security_headers_csp_present():
    """Content-Security-Policy must be present in responses."""

    async def hello(request: Request):
        return PlainTextResponse("Hello")

    app = Starlette(
        routes=[Route("/hello", hello, methods=["GET"])],
        middleware=[Middleware(SecurityHeadersMiddleware)],
    )
    client = TestClient(app)
    response = client.get("/hello")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src" in csp
    assert "'self'" in csp


def test_security_headers_hsts_only_in_production():
    """HSTS header should only appear when enabled (production)."""

    async def hello(request: Request):
        return PlainTextResponse("Hello")

    orig_hsts = config.security.hsts_enabled
    try:
        config.security.hsts_enabled = True
        app = Starlette(
            routes=[Route("/hello", hello, methods=["GET"])],
            middleware=[Middleware(SecurityHeadersMiddleware)],
        )
        client = TestClient(app)
        response = client.get("/hello")
        assert "Strict-Transport-Security" in response.headers
    finally:
        config.security.hsts_enabled = orig_hsts


def test_error_messages_no_secret_leakage():
    """Token error messages must not leak the secret key."""
    import pytest

    secret = "my-super-secret-key-12345"
    token = create_access_token({"sub": 1}, secret_key=secret)
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(token, secret_key="wrong-key")
    msg = str(exc_info.value)
    assert "my-super-secret-key-12345" not in msg
    assert "secret" not in msg.lower()


def test_password_hash_uses_constant_time():
    """Password verification must use constant-time comparison (secrets.compare_digest)."""
    import inspect

    import voodoo.auth as auth_mod

    # Verify the function uses secrets.compare_digest by checking the source
    source = inspect.getsource(auth_mod.verify_password)
    assert "compare_digest" in source


def test_csrf_exempt_api_key_requests():
    """CSRF should exempt M2M requests with API key headers."""
    config.security.csrf_enabled = True
    try:

        async def post_action(request: Request):
            return JSONResponse({"saved": True})

        app = Starlette(
            routes=[Route("/action", post_action, methods=["POST"])],
            middleware=[Middleware(CSRFMiddleware)],
        )
        client = TestClient(app)

        # POST with Bearer token is exempt
        r = client.post(
            "/action",
            headers={"Authorization": "Bearer some.jwt.token"},
        )
        assert r.status_code == 200

        # POST with API key is exempt
        r2 = client.post("/action", headers={"X-API-Key": "vd_live_test_key"})
        assert r2.status_code == 200
    finally:
        config.security.csrf_enabled = False
