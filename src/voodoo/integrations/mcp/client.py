from __future__ import annotations

import itertools
import json
import math
from typing import Any
from urllib.parse import urlsplit

_DEFAULT_TIMEOUT_SECONDS = 15.0
_MAX_TIMEOUT_SECONDS = 300.0
_DEFAULT_MAX_RESPONSE_BYTES = 1 * 1024 * 1024
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class MCPClient:
    """Small async MCP client with bounded network behavior."""

    def __init__(
        self,
        endpoint_url: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
    ):
        parsed = urlsplit(endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCP endpoint must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("MCP endpoint must not embed credentials")
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(float(timeout))
            or timeout <= 0
            or timeout > _MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(f"MCP timeout must be between 0 and {_MAX_TIMEOUT_SECONDS:g} seconds")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or max_response_bytes <= 0
            or max_response_bytes > _MAX_RESPONSE_BYTES
        ):
            raise ValueError(
                f"MCP max_response_bytes must be between 1 and {_MAX_RESPONSE_BYTES}"
            )
        self.endpoint_url = endpoint_url
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self._request_ids = itertools.count(1)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        import httpx

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
                "id": next(self._request_ids),
            }
            chunks: list[bytes] = []
            total = 0
            async with client.stream("POST", self.endpoint_url, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.max_response_bytes:
                        raise ValueError("MCP response exceeds the configured size limit")
                    chunks.append(chunk)
            try:
                result = json.loads(b"".join(chunks))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("MCP response must be valid JSON") from exc
            if not isinstance(result, dict):
                raise ValueError("MCP response must be a JSON object")
            return result
