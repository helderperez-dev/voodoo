from typing import Any


class MCPClient:
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        import httpx

        async with httpx.AsyncClient() as client:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
                "id": 1,
            }
            response = await client.post(self.endpoint_url, json=payload)
            return response.json()
