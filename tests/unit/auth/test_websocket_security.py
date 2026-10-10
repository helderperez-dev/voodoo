from __future__ import annotations

from types import SimpleNamespace

from voodoo.ui.events import _origin_allowed, _websocket_principal


def _websocket(origin: str | None, host: str = "app.example"):
    headers = {"host": host}
    if origin is not None:
        headers["origin"] = origin
    return SimpleNamespace(headers=headers, cookies={}, app=SimpleNamespace())


def _config(*, env: str = "production", origins: list[str] | None = None):
    return SimpleNamespace(
        env=env,
        security=SimpleNamespace(cors_origins=origins or ["https://trusted.example"]),
        auth=SimpleNamespace(cookie_name="voodoo_auth", secret_key="x" * 32),
    )


def test_websocket_origin_policy_is_fail_closed_in_production():
    config = _config()
    assert _origin_allowed(_websocket(None), config) is False
    assert _origin_allowed(_websocket("https://evil.example"), config) is False
    assert _origin_allowed(_websocket("https://trusted.example"), config) is True
    assert _origin_allowed(_websocket("https://app.example"), config) is True


def test_websocket_origin_without_header_is_allowed_only_outside_production():
    assert _origin_allowed(_websocket(None), _config(env="test")) is True


def test_invalid_websocket_auth_cookie_does_not_create_a_principal():
    websocket = _websocket("https://app.example")
    websocket.cookies["voodoo_auth"] = "not-a-token"
    assert _websocket_principal(websocket, _config()) is None
