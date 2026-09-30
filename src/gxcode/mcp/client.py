"""MCP 客户端 — 三步会话：initialize → list_tools → call_tool"""

from gxcode.mcp.transport import JsonRpcTransport


class McpClient:
    """MCP JSON-RPC 客户端"""

    def __init__(self, transport: JsonRpcTransport, name: str = ""):
        self._transport = transport
        self.name = name
        self._next_id = 1
        self._server_info = {}

    async def connect(self) -> None:
        """建立连接（stdio 需单独调用 connect）"""
        if hasattr(self._transport, "connect"):
            await self._transport.connect()

    async def initialize(self) -> dict:
        """初始化握手"""
        result = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "GXCode", "version": "1.0.0"},
        })
        self._server_info = result
        # 发送 initialized 通知
        await self._notify("notifications/initialized", {})
        return result

    async def list_tools(self) -> list[dict]:
        """列出工具"""
        result = await self._request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """调用工具"""
        return await self._request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

    async def _request(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC 请求，等待响应"""
        if not self._transport:
            raise RuntimeError(f"MCP 客户端 '{self.name}' 传输层未初始化")
        msg_id = self._next_id
        self._next_id += 1

        await self._transport.send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params,
        })

        response = await self._transport.receive()
        if "error" in response:
            raise RuntimeError(f"MCP 错误: {response['error']}")
        return response.get("result", {})

    async def _notify(self, method: str, params: dict) -> None:
        """发送 JSON-RPC 通知（无 id，不等待响应）"""
        if not self._transport:
            raise RuntimeError(f"MCP 客户端 '{self.name}' 传输层未初始化")
        await self._transport.send({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

    async def close(self) -> None:
        await self._transport.close()