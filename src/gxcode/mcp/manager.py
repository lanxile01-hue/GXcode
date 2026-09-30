"""MCP 客户端管理器 — 多 Server 连接和生命周期"""

from gxcode.mcp.adapter import MCPToolWrapper
from gxcode.mcp.client import McpClient
from gxcode.mcp.transport import HttpTransport, StdioTransport
from gxcode.tools import ToolRegistry

import logging

logger = logging.getLogger(__name__)


class MCPManager:
    """管理多个 MCP Server 的连接和工具注册"""

    def __init__(self):
        self._clients: list[McpClient] = []

    async def connect_all(self, server_configs: dict) -> ToolRegistry:
        """连接所有 Server，发现工具，注册到 ToolRegistry

        Args:
            server_configs: {"name": {"type": "stdio", ...}, ...}

        Returns:
            包含 MCP 工具 + 默认工具的工具注册中心
        """
        from gxcode.tools import create_default_registry
        registry = create_default_registry()

        for name, cfg in server_configs.items():
            try:
                client = await self._connect_one(name, cfg)
                if client:
                    self._clients.append(client)
                    tools = await client.list_tools()
                    for tool_def in tools:
                        wrapper = MCPToolWrapper(client, tool_def)
                        registry.register(wrapper)
                    logger.info("MCP Server '%s' 已连接，注册 %d 个工具", name, len(tools))
            except Exception:
                logger.warning("MCP Server '%s' 连接失败，已跳过", name, exc_info=True)

        return registry

    async def _connect_one(self, name: str, cfg: dict) -> McpClient | None:
        """连接单个 Server"""
        server_type = cfg.get("type", "stdio")

        if server_type == "stdio":
            transport = StdioTransport(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
        elif server_type == "http":
            transport = HttpTransport(
                url=cfg["url"],
                headers=cfg.get("headers"),
            )
        else:
            return None

        client = McpClient(transport, name=name)
        await client.connect()
        await client.initialize()
        return client

    async def close_all(self) -> None:
        for client in self._clients:
            await client.close()