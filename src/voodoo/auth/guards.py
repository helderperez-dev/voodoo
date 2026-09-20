import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from voodoo.auth.user import get_current_user


def _request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request | None:
    req = kwargs.get("request")
    if isinstance(req, Request):
        return req
    if args and isinstance(args[0], Request):
        return args[0]
    return None


def _unauthenticated(req: Request | None, redirect_url: str | None = None) -> Any:
    if req and redirect_url and "text/html" in req.headers.get("accept", ""):
        return RedirectResponse(url=redirect_url, status_code=302)
    return JSONResponse(
        {"error": "Authentication required", "code": 401}, status_code=401
    )


def _inject_user(sig: inspect.Signature, kwargs: dict[str, Any], user: Any) -> None:
    if "user" in sig.parameters and "user" not in kwargs:
        kwargs["user"] = user


def _guard(
    check: Callable[[Any], Any | None],
    redirect_url: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)

        def authorize(
            args: tuple[Any, ...], kwargs: dict[str, Any]
        ) -> tuple[Any, Any | None]:
            req = _request(args, kwargs)
            user = get_current_user(req)
            if not user or not user.is_authenticated:
                return None, _unauthenticated(req, redirect_url)
            denied = check(user)
            if denied is not None:
                return None, denied
            _inject_user(sig, kwargs, user)
            return user, None

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            _, denied = authorize(args, kwargs)
            if denied is not None:
                return denied
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            _, denied = authorize(args, kwargs)
            if denied is not None:
                return denied
            return func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def require_auth(
    redirect_url: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require an authenticated user."""
    return _guard(lambda _user: None, redirect_url)


def require_roles(
    *roles: str, redirect_url: str | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require the user to hold one of the specified roles."""

    def check(user: Any) -> Any | None:
        if user.has_role(*roles):
            return None
        return JSONResponse(
            {
                "error": "Forbidden: Insufficient role permissions",
                "code": 403,
                "required_roles": list(roles),
            },
            status_code=403,
        )

    return _guard(check, redirect_url)


def require_scopes(*scopes: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require specific API key scopes or permissions."""

    def check(user: Any) -> Any | None:
        if user.has_scope(*scopes):
            return None
        return JSONResponse(
            {
                "error": "Forbidden: Missing required scope",
                "code": 403,
                "required_scopes": list(scopes),
            },
            status_code=403,
        )

    return _guard(check)


def require_api_key(
    scopes: list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Enforce machine-to-machine API key authentication."""

    def check(user: Any) -> Any | None:
        if user.auth_type != "api_key":
            return JSONResponse(
                {"error": "Valid API Key required", "code": 401}, status_code=401
            )
        if scopes and not user.has_scope(*scopes):
            return JSONResponse(
                {"error": "Forbidden: Insufficient API key permissions", "code": 403},
                status_code=403,
            )
        return None

    return _guard(check)


login_required = require_auth
requires_role = require_roles
requires_roles = require_roles
requires_permission = require_scopes
requires_permissions = require_scopes
requires_scopes = require_scopes
requires_api_key = require_api_key
