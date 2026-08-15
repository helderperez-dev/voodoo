import asyncio
import os
import pytest
import time
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.testclient import TestClient

from voodoo.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
    verify_api_key,
    generate_secret_key,
    AuthUser,
    User,
    get_current_user,
    current_user,
    set_auth_cookie,
    clear_auth_cookie,
    require_auth,
    require_roles,
    require_scopes,
    require_api_key,
    AuthMiddleware,
    AuthError,
    ExpiredTokenError,
    InvalidTokenError,
    PermissionDeniedError,
)
from voodoo.data import BaseModel, init_db, rls_policy, get_db
from voodoo.config import config


def test_password_hashing():
    pwd = "SuperSecretPassword123!"
    hashed = hash_password(pwd)

    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(pwd, "invalid$format") is False
    assert verify_password(pwd, "") is False


def test_jwt_token_generation_and_verification():
    secret = "test-secret-key-123456"
    payload = {"sub": 42, "email": "user@example.com", "role": "admin"}

    token = create_access_token(payload, expires_delta_seconds=60, secret_key=secret)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = decode_access_token(token, secret_key=secret)
    assert decoded["sub"] == 42
    assert decoded["email"] == "user@example.com"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded

    # Tampered signature
    with pytest.raises(InvalidTokenError):
        decode_access_token(token + "tampered", secret_key=secret)

    # Wrong secret key
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret_key="wrong-secret")

    # Expired token
    expired_token = create_access_token(
        payload, expires_delta_seconds=-10, secret_key=secret
    )
    with pytest.raises(ExpiredTokenError):
        decode_access_token(expired_token, secret_key=secret)


def test_api_key_generation_and_verification():
    raw_key, key_hash = generate_api_key(prefix="vd_live")
    assert raw_key.startswith("vd_live_")
    assert hash_api_key(raw_key) == key_hash
    assert verify_api_key(raw_key, key_hash) is True
    assert verify_api_key("vd_live_invalidkey", key_hash) is False
    assert verify_api_key("", key_hash) is False
    assert verify_api_key(raw_key, "") is False


def test_secret_key_generation():
    key = generate_secret_key(32)
    assert isinstance(key, str)
    assert len(key) == 64  # 32 bytes in hex = 64 chars


def test_auth_user_class():
    user = AuthUser(
        id=1,
        email="admin@test.com",
        username="admin",
        role="admin",
        roles=["admin", "editor"],
        scopes=["read", "write", "admin:all"],
        is_authenticated=True,
    )

    assert user.is_authenticated is True
    assert user.has_role("admin") is True
    assert user.has_role("editor") is True
    assert user.has_role("viewer") is False
    assert user.has_scope("read") is True
    assert user.has_scope("delete") is False

    unauth = AuthUser(is_authenticated=False)
    assert unauth.has_role("admin") is False
    assert unauth.has_scope("read") is False


@pytest.mark.asyncio
async def test_user_database_model(tmp_path):
    db_file = str(tmp_path / "test_auth.db")
    config.db_path = db_file
    await init_db(db_file)

    # Create user
    user, raw_key = await User.create_user(
        email="alice@example.com",
        password="AliceSecurePassword!1",
        username="alice",
        role="admin",
    )
    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.username == "alice"
    assert user.role == "admin"
    assert raw_key.startswith("vd_live_")

    # Authenticate by email
    authed_by_email = await User.authenticate(
        "alice@example.com", "AliceSecurePassword!1"
    )
    assert authed_by_email is not None
    assert authed_by_email.id == user.id

    # Authenticate by username
    authed_by_uname = await User.authenticate("alice", "AliceSecurePassword!1")
    assert authed_by_uname is not None
    assert authed_by_uname.id == user.id

    # Failed auth
    failed = await User.authenticate("alice@example.com", "WrongPassword")
    assert failed is None

    # Find by API key
    by_key = await User.find_by_api_key(raw_key)
    assert by_key is not None
    assert by_key.id == user.id

    # Convert to AuthUser
    auth_user = user.to_auth_user()
    assert auth_user.is_authenticated is True
    assert auth_user.role == "admin"


def test_cookie_helpers():
    resp1 = Response(content="ok")
    set_auth_cookie(resp1, "test.token.jwt", max_age=3600)

    cookie_header = resp1.headers.get("set-cookie", "")
    assert config.auth.cookie_name in cookie_header
    assert "test.token.jwt" in cookie_header
    assert "HttpOnly" in cookie_header

    resp2 = Response(content="logout")
    clear_auth_cookie(resp2)
    cookie_header2 = resp2.headers.get("set-cookie", "")
    assert config.auth.cookie_name in cookie_header2
    assert "Max-Age=0" in cookie_header2 or "expires=" in cookie_header2.lower()


def test_auth_middleware_and_guards(tmp_path):
    db_file = str(tmp_path / "test_auth_mw.db")
    config.db_path = db_file
    asyncio.run(init_db(db_file))

    # Pre-create user in DB
    created_user, api_key = asyncio.run(
        User.create_user(
            email="bob@example.com",
            password="BobPassword123!",
            username="bob",
            role="editor",
        )
    )

    @require_auth()
    async def protected_endpoint(request: Request, user: AuthUser):
        return JSONResponse({"message": f"Hello {user.username}", "role": user.role})

    @require_roles("admin")
    async def admin_only_endpoint(request: Request, user: AuthUser):
        return JSONResponse({"admin": True})

    @require_api_key()
    async def m2m_endpoint(request: Request, user: AuthUser):
        return JSONResponse({"api_ok": True, "auth_type": user.auth_type})

    routes = [
        Route("/protected", protected_endpoint, methods=["GET"]),
        Route("/admin", admin_only_endpoint, methods=["GET"]),
        Route("/m2m", m2m_endpoint, methods=["GET"]),
    ]

    app = Starlette(routes=routes, middleware=[Middleware(AuthMiddleware)])
    client = TestClient(app)

    # 1. Unauthenticated request to /protected
    r1 = client.get("/protected")
    assert r1.status_code == 401

    # 2. Authenticated via Bearer JWT token
    token = create_access_token(
        {"sub": created_user.id, "username": "bob", "role": "editor"}
    )
    r2 = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["message"] == "Hello bob"
    assert r2.json()["role"] == "editor"

    # 3. Role check failed: bob is editor, not admin
    r3 = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 403

    # 4. Authenticated via API Key header
    r4 = client.get("/m2m", headers={"X-API-Key": api_key})
    assert r4.status_code == 200
    assert r4.json()["api_ok"] is True
    assert r4.json()["auth_type"] == "api_key"

    # 5. Authenticated via session cookie
    r5 = client.get("/protected", cookies={config.auth.cookie_name: token})
    assert r5.status_code == 200
    assert r5.json()["message"] == "Hello bob"


@pytest.mark.asyncio
async def test_rls_auto_user_context(tmp_path):
    db_file = str(tmp_path / "test_rls.db")
    config.db_path = db_file
    await init_db(db_file)

    class Document(BaseModel):
        id: int
        title: str
        owner_id: int

    @rls_policy(Document)
    def document_policy(context: dict):
        uid = context.get("id")
        return f"owner_id = {uid}" if uid else "1=0"

    await Document._create_table()

    doc1 = Document()
    doc1.title = "Alice Doc"
    doc1.owner_id = 1
    await doc1.insert()

    doc2 = Document()
    doc2.title = "Bob Doc"
    doc2.owner_id = 2
    await doc2.insert()

    # Set current_user context var as Alice
    alice_auth = AuthUser(id=1, email="alice@test.com", is_authenticated=True)
    t = current_user.set(alice_auth)
    try:
        docs = await Document.find_all()
        assert len(docs) == 1
        assert docs[0].title == "Alice Doc"
    finally:
        current_user.reset(t)
