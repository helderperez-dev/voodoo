from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from voodoo.integrations.mcp.client import MCPClient


def test_mcp_client_rejects_unsafe_endpoint_configuration() -> None:
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        MCPClient("file:///tmp/mcp")
    with pytest.raises(ValueError, match="credentials"):
        MCPClient("https://user:password@example.test/mcp")
    with pytest.raises(ValueError, match="timeout"):
        MCPClient("https://example.test/mcp", timeout=301)
    with pytest.raises(ValueError, match="max_response_bytes"):
        MCPClient("https://example.test/mcp", max_response_bytes=0)


@pytest.mark.asyncio
async def test_mcp_client_bounds_request_and_response(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class Response:
        content = b'{"result": {"ok": true}}'

        def raise_for_status(self) -> None:
            calls["status_checked"] = True


        async def aiter_bytes(self):
            yield self.content

    class AsyncClient:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def stream(self, method, url, *, json):
            calls["request"] = (url, json)
            response = Response()

            class Stream:
                async def __aenter__(self):
                    return response

                async def __aexit__(self, *_args):
                    return False

            return Stream()

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(AsyncClient=AsyncClient))
    client = MCPClient("https://example.test/mcp", timeout=4, max_response_bytes=128)
    result = await client.call_tool("search", {"query": "voodoo"})

    assert result == {"result": {"ok": True}}
    assert calls["client_kwargs"] == {"timeout": 4.0, "follow_redirects": False}
    assert calls["status_checked"] is True
    assert calls["request"][0] == "https://example.test/mcp"
    assert calls["request"][1]["id"] == 1

    await client.call_tool("search", {"query": "again"})
    assert calls["request"][1]["id"] == 2


@pytest.mark.asyncio
async def test_mcp_client_rejects_oversized_response(monkeypatch) -> None:
    class Response:
        content = b"x" * 32

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            yield self.content

    class AsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def stream(self, *_args, **_kwargs):
            response = Response()

            class Stream:
                async def __aenter__(self):
                    return response

                async def __aexit__(self, *_args):
                    return False

            return Stream()

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(AsyncClient=AsyncClient))
    with pytest.raises(ValueError, match="size limit"):
        await MCPClient("https://example.test/mcp", max_response_bytes=16).call_tool(
            "search", {}
        )
