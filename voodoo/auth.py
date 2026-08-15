import base64
import hashlib
import hmac
import inspect
import json
import secrets
import time
from collections.abc import Callable
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Literal, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from voodoo.config import config
from voodoo.data import BaseModel, get_db

# Context variable for the currently authenticated user in the current async task
current_user: ContextVar[Optional["AuthUser"]] = ContextVar(
    "current_user", default=None
)


class AuthError(Exception):
    """Base exception for authentication errors."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InvalidCredentialsError(AuthError):
    pass


class ExpiredTokenError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


class PermissionDeniedError(AuthError):
    def __init__(self, message: str = "Permission denied", status_code: int = 403):
        super().__init__(message, status_code=status_code)


# =========================================================================
# Cryptographic Password Hashing (Zero-dependency PBKDF2-HMAC-SHA256)
# =========================================================================


def hash_password(
    password: str, salt: str | None = None, iterations: int = 600_000
) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP standard).
    Format: pbkdf2_sha256$<iterations>$<salt>$<hex_hash>
    """
    if salt is None:
        salt = secrets.token_hex(16)

    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    hash_hex = dk.hex()
    return f"pbkdf2_sha256${iterations}${salt}${hash_hex}"


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a PBKDF2-HMAC-SHA256 hash using constant-time comparison.
    """
    if not hashed_password or not isinstance(hashed_password, str):
        return False

    parts = hashed_password.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False

    try:
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
    except (ValueError, IndexError):
        return False

    computed_dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    computed_hex = computed_dk.hex()
    return secrets.compare_digest(computed_hex, expected_hash)


# =========================================================================
# JWT / HMAC-SHA256 Signed Access Tokens
# =========================================================================


def _b64encode_str(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode_str(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(
    data: dict[str, Any],
    expires_delta_seconds: int | None = None,
    secret_key: str | None = None,
) -> str:
    """
    Creates an HMAC-SHA256 signed access token (JWT format).
    """
    secret = secret_key or config.auth.secret_key
    expiry = (
        expires_delta_seconds
        if expires_delta_seconds is not None
        else config.auth.token_expiry_seconds
    )

    now = int(time.time())
    payload = data.copy()
    payload["iat"] = now
    if "exp" not in payload and expiry is not None and expiry != 0:
        payload["exp"] = now + expiry

    header = {"alg": "HS256", "typ": "JWT"}

    header_b64 = _b64encode_str(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = _b64encode_str(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    message = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    sig_b64 = _b64encode_str(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str, secret_key: str | None = None) -> dict[str, Any]:
    """
    Decodes and validates an HMAC-SHA256 signed access token.
    Raises ExpiredTokenError or InvalidTokenError if invalid.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Missing or invalid token")

    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidTokenError("Invalid token format")

    header_b64, payload_b64, sig_b64 = parts
    secret = secret_key or config.auth.secret_key

    message = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()

    try:
        provided_sig = _b64decode_str(sig_b64)
    except Exception:
        raise InvalidTokenError("Corrupted token signature encoding") from None

    if not secrets.compare_digest(expected_sig, provided_sig):
        raise InvalidTokenError("Invalid token signature")

    try:
        payload_bytes = _b64decode_str(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise InvalidTokenError("Malformed token payload") from None

    if not isinstance(payload, dict):
        raise InvalidTokenError("Malformed token payload")

    if "exp" in payload:
        now = int(time.time())
        if now > payload["exp"]:
            raise ExpiredTokenError("Token has expired")

    return payload


# =========================================================================
# API Key Management (Prefix + High-Entropy Random + SHA256 Hash)
# =========================================================================


def generate_api_key(prefix: str | None = None) -> tuple[str, str]:
    """
    Generates a secure API key with prefix and its SHA-256 hash.
    Returns: (raw_key, key_hash)
    Example: ("vd_live_4a89fb...", "c59600a7...")
    """
    pref = prefix or config.auth.api_key_prefix
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{pref}_{random_part}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash


def hash_api_key(api_key: str) -> str:
    """Computes deterministic SHA-256 hash of an API key for safe database storage."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """Constant-time verification of an API key against stored hash."""
    if not api_key or not key_hash:
        return False
    computed_hash = hash_api_key(api_key)
    return secrets.compare_digest(computed_hash, key_hash)


def generate_secret_key(length: int = 32) -> str:
    """Generates a cryptographically strong random hex secret key."""
    return secrets.token_hex(length)


# =========================================================================
# Auth User & Context
# =========================================================================


class AuthUser:
    """Represents an authenticated user identity in the request context."""

    def __init__(
        self,
        id: int | str | None = None,
        email: str | None = None,
        username: str | None = None,
        role: str = "user",
        roles: list[str] | None = None,
        scopes: list[str] | None = None,
        auth_type: str = "anonymous",
        is_authenticated: bool = False,
        raw_data: dict[str, Any] | None = None,
    ):
        self.id = id
        self.email = email
        self.username = username
        self.role = role
        self.roles = roles or ([role] if role else [])
        if role and role not in self.roles:
            self.roles.append(role)
        self.scopes = scopes or []
        self.auth_type = auth_type
        self.is_authenticated = is_authenticated
        self.raw_data = raw_data or {}

    def has_role(self, *required_roles: str) -> bool:
        """Checks if the user has at least one of the required roles."""
        if not self.is_authenticated:
            return False
        return any(r in self.roles for r in required_roles)

    def has_scope(self, *required_scopes: str) -> bool:
        """Checks if the user has all required scopes."""
        if not self.is_authenticated:
            return False
        return all(s in self.scopes for s in required_scopes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "role": self.role,
            "roles": self.roles,
            "scopes": self.scopes,
            "auth_type": self.auth_type,
            "is_authenticated": self.is_authenticated,
        }

    def __repr__(self) -> str:
        return f"<AuthUser id={self.id} email={self.email} role={self.role} authenticated={self.is_authenticated}>"


def get_current_user(request: Request | None = None) -> AuthUser | None:
    """
    Retrieves the currently authenticated user from request state or ContextVar.
    """
    if (
        request is not None
        and hasattr(request, "state")
        and hasattr(request.state, "user")
    ):
        u = getattr(request.state, "user", None)
        if isinstance(u, AuthUser):
            return u
    return current_user.get()


# =========================================================================
# Built-in User Database Model (extends Voodoo BaseModel)
# =========================================================================


class User(BaseModel):
    """Built-in User entity for relational SQLite storage."""

    __tablename__ = "voodoo_users"
    id: int
    email: str
    username: str
    hashed_password: str
    role: str
    is_active: bool
    api_key_hash: str
    created_at: str

    @classmethod
    async def create_user(
        cls,
        email: str,
        password: str,
        username: str | None = None,
        role: str = "user",
        api_key_prefix: str | None = None,
    ) -> tuple["User", str | None]:
        """
        Creates and stores a new User in the database with hashed password.
        Optionally generates an initial API key.
        Returns (user, raw_api_key)
        """
        _ = await get_db()
        # Ensure table exists
        await cls._create_table()

        hashed = hash_password(password)
        uname = username or email.split("@")[0]
        raw_key, key_hash = generate_api_key(api_key_prefix)
        created = datetime.now(UTC).isoformat()

        user = cls()
        user.email = email
        user.username = uname
        user.hashed_password = hashed
        user.role = role
        user.is_active = True
        user.api_key_hash = key_hash
        user.created_at = created

        await user.insert()
        return user, raw_key

    @classmethod
    async def authenticate(
        cls, email_or_username: str, password: str
    ) -> Optional["User"]:
        """Authenticates user by email/username and password."""
        db = await get_db()
        await cls._create_table()

        query = "SELECT * FROM voodoo_users WHERE (email = ? OR username = ?) AND is_active = 1"
        async with db.execute(query, [email_or_username, email_or_username]) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            user = cls()
            for k in row.keys():
                val = row[k]
                if k == "is_active":
                    val = bool(val)
                setattr(user, k, val)

            if verify_password(password, user.hashed_password):
                return user
            return None

    @classmethod
    async def find_by_api_key(cls, api_key: str) -> Optional["User"]:
        """Finds active user by matching API key hash."""
        db = await get_db()
        await cls._create_table()

        key_hash = hash_api_key(api_key)
        query = "SELECT * FROM voodoo_users WHERE api_key_hash = ? AND is_active = 1"
        async with db.execute(query, [key_hash]) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            user = cls()
            for k in row.keys():
                val = row[k]
                if k == "is_active":
                    val = bool(val)
                setattr(user, k, val)
            return user

    def to_auth_user(self, auth_type: str = "session") -> AuthUser:
        return AuthUser(
            id=self.id,
            email=self.email,
            username=self.username,
            role=self.role,
            roles=[self.role] if self.role else [],
            scopes=["*"] if self.role == "admin" else ["read", "write"],
            auth_type=auth_type,
            is_authenticated=True,
            raw_data={
                "id": self.id,
                "email": self.email,
                "username": self.username,
                "role": self.role,
            },
        )


# =========================================================================
# Cookie Helpers
# =========================================================================


def _normalize_samesite(val: str | None) -> Literal["lax", "strict", "none"]:
    if val and val.lower() in ("lax", "strict", "none"):
        return val.lower()  # type: ignore[return-value]
    return "lax"


def set_auth_cookie(
    response: Response,
    token: str,
    max_age: int | None = None,
    cookie_name: str | None = None,
    samesite: Literal["lax", "strict", "none"] | None = None,
) -> None:
    """Sets a secure HTTP-only authentication cookie on the response."""
    c_name = cookie_name or config.auth.cookie_name
    c_max_age = max_age if max_age is not None else config.auth.token_expiry_seconds
    ss = samesite or _normalize_samesite(config.auth.cookie_samesite)

    response.set_cookie(
        key=c_name,
        value=token,
        max_age=c_max_age,
        path="/",
        secure=config.auth.cookie_secure,
        httponly=config.auth.cookie_httponly,
        samesite=ss,
    )


def clear_auth_cookie(
    response: Response,
    cookie_name: str | None = None,
    samesite: Literal["lax", "strict", "none"] | None = None,
) -> None:
    """Clears the authentication cookie."""
    c_name = cookie_name or config.auth.cookie_name
    ss = samesite or _normalize_samesite(config.auth.cookie_samesite)
    response.delete_cookie(
        key=c_name,
        path="/",
        secure=config.auth.cookie_secure,
        httponly=config.auth.cookie_httponly,
        samesite=ss,
    )


# =========================================================================
# Route Decorators & Guards
# =========================================================================


def require_auth(  # noqa: C901
    redirect_url: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for API endpoints or Page views requiring authenticated user.
    If unauthenticated:
      - Returns 401 JSONResponse for API calls / JSON requests
      - Redirects to redirect_url (or /login) if HTML browser request
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Resolve request object
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated:
                if (
                    req
                    and "text/html" in req.headers.get("accept", "")
                    and redirect_url
                ):
                    return RedirectResponse(url=redirect_url, status_code=302)
                return JSONResponse(
                    {"error": "Authentication required", "code": 401}, status_code=401
                )

            # Inject user if in signature
            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated:
                if (
                    req
                    and "text/html" in req.headers.get("accept", "")
                    and redirect_url
                ):
                    return RedirectResponse(url=redirect_url, status_code=302)
                return JSONResponse(
                    {"error": "Authentication required", "code": 401}, status_code=401
                )

            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            return func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def require_roles(  # noqa: C901
    *roles: str, redirect_url: str | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator requiring the user to hold one of the specified roles.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:  # noqa: C901
        sig = inspect.signature(func)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated:
                if (
                    req
                    and "text/html" in req.headers.get("accept", "")
                    and redirect_url
                ):
                    return RedirectResponse(url=redirect_url, status_code=302)
                return JSONResponse(
                    {"error": "Authentication required", "code": 401}, status_code=401
                )

            if not user.has_role(*roles):
                return JSONResponse(
                    {
                        "error": "Forbidden: Insufficient role permissions",
                        "code": 403,
                        "required_roles": list(roles),
                    },
                    status_code=403,
                )

            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated:
                if (
                    req
                    and "text/html" in req.headers.get("accept", "")
                    and redirect_url
                ):
                    return RedirectResponse(url=redirect_url, status_code=302)
                return JSONResponse(
                    {"error": "Authentication required", "code": 401}, status_code=401
                )

            if not user.has_role(*roles):
                return JSONResponse(
                    {
                        "error": "Forbidden: Insufficient role permissions",
                        "code": 403,
                        "required_roles": list(roles),
                    },
                    status_code=403,
                )

            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            return func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def require_scopes(*scopes: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:  # noqa: C901
    """Decorator requiring specific API key scopes / permissions."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated:
                return JSONResponse(
                    {"error": "Authentication required", "code": 401}, status_code=401
                )

            if not user.has_scope(*scopes):
                return JSONResponse(
                    {
                        "error": "Forbidden: Missing required scope",
                        "code": 403,
                        "required_scopes": list(scopes),
                    },
                    status_code=403,
                )

            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated:
                return JSONResponse(
                    {"error": "Authentication required", "code": 401}, status_code=401
                )

            if not user.has_scope(*scopes):
                return JSONResponse(
                    {
                        "error": "Forbidden: Missing required scope",
                        "code": 403,
                        "required_scopes": list(scopes),
                    },
                    status_code=403,
                )

            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            return func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def require_api_key(
    scopes: list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator enforcing machine-to-machine API key authentication."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            req = kwargs.get("request") or (
                args[0] if args and isinstance(args[0], Request) else None
            )
            user = get_current_user(req)

            if not user or not user.is_authenticated or user.auth_type != "api_key":
                return JSONResponse(
                    {"error": "Valid API Key required", "code": 401}, status_code=401
                )

            if scopes and not user.has_scope(*scopes):
                return JSONResponse(
                    {
                        "error": "Forbidden: Insufficient API key permissions",
                        "code": 403,
                    },
                    status_code=403,
                )

            if "user" in sig.parameters and "user" not in kwargs:
                kwargs["user"] = user

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Convenient aliases for routing and controllers
login_required = require_auth
requires_role = require_roles
requires_roles = require_roles
requires_permission = require_scopes
requires_permissions = require_scopes
requires_scopes = require_scopes
requires_api_key = require_api_key


# =========================================================================
# ASGI Auth Middleware
# =========================================================================


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extracts and authenticates user from:
    1. Authorization: Bearer <token>
    2. X-API-Key: <key> or Authorization: ApiKey <key>
    3. Session cookie (voodoo_auth)

    Populates request.state.user and current_user ContextVar.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        user = AuthUser(is_authenticated=False)
        auth_header = request.headers.get("Authorization", "").strip()
        api_key_header = request.headers.get("X-API-Key", "").strip()
        cookie_val = request.cookies.get(config.auth.cookie_name)

        # 1. Check API Key Header
        if api_key_header:
            db_user = await User.find_by_api_key(api_key_header)
            if db_user:
                user = db_user.to_auth_user(auth_type="api_key")
            else:
                # Invalid API key
                user = AuthUser(
                    id=None,
                    username="api_client",
                    role="service",
                    roles=["service"],
                    scopes=["read", "write"],
                    auth_type="api_key",
                    is_authenticated=False,
                )
        # 2. Check Bearer Token or ApiKey in Authorization Header
        elif auth_header:
            if auth_header.startswith("Bearer "):
                token_str = auth_header[7:].strip()
                try:
                    payload = decode_access_token(token_str)
                    user = AuthUser(
                        id=payload.get("sub") or payload.get("id"),
                        email=payload.get("email"),
                        username=payload.get("username"),
                        role=payload.get("role", "user"),
                        roles=payload.get("roles", [payload.get("role", "user")]),
                        scopes=payload.get("scopes", []),
                        auth_type="token",
                        is_authenticated=True,
                        raw_data=payload,
                    )
                except AuthError:
                    user = AuthUser(is_authenticated=False)
            elif auth_header.startswith("ApiKey "):
                raw_key = auth_header[7:].strip()
                db_user = await User.find_by_api_key(raw_key)
                if db_user:
                    user = db_user.to_auth_user(auth_type="api_key")
        # 3. Check Session Cookie
        elif cookie_val:
            try:
                payload = decode_access_token(cookie_val)
                user = AuthUser(
                    id=payload.get("sub") or payload.get("id"),
                    email=payload.get("email"),
                    username=payload.get("username"),
                    role=payload.get("role", "user"),
                    roles=payload.get("roles", [payload.get("role", "user")]),
                    scopes=payload.get("scopes", []),
                    auth_type="session",
                    is_authenticated=True,
                    raw_data=payload,
                )
            except AuthError:
                user = AuthUser(is_authenticated=False)

        # Set request state and task context variable
        request.state.user = user
        ctx_token: Token[AuthUser | None] = current_user.set(user)
        try:
            response = await call_next(request)
            return response
        finally:
            current_user.reset(ctx_token)
