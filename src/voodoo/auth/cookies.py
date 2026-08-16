from typing import Literal

from starlette.responses import Response

from voodoo.config import config

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
