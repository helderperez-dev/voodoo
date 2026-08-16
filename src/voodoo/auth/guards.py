import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from voodoo.auth.user import get_current_user

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
