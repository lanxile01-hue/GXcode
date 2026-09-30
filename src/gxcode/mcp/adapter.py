"""MCP Tool 适配器 — 把远端工具包装成 GXCode Tool 接口"""

import json

from gxcode.tools.base import Tool, ToolResult


class MCPToolWrapper(Tool):
    """包装 MCP 远端工具为 GXCode Tool"""

    def __init__(self, client, tool_def: dict):
        self._client = client
        self._tool_def = tool_def

        # 从 MCP tool 定义映射到 Tool 接口
        self.name = tool_def.get("name", "")
        self.description = tool_def.get("description", "")
        self.is_safe = False  # 远端工具默认不安全

        # 构建 JSON Schema
        input_schema = tool_def.get("inputSchema", {})
        self.parameters = input_schema if input_schema else {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        try:
            result = await self._client.call_tool(self.name, kwargs)
            # MCP call_tool 返回 content 列表
            content = result.get("content", [])
            texts = []
            for item in content:
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
            return ToolResult.ok("\n".join(texts) if texts else json.dumps(result))
        except Exception as e:
            return ToolResult.fail(str(e))