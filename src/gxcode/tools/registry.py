"""GXCode 工具注册中心

集中管理工具实例，提供查找和 API schema 生成。
"""

from gxcode.tools.base import Tool


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """按名查找工具，不存在抛 KeyError"""
        if name not in self._tools:
            raise KeyError(f"工具 '{name}' 未注册，可用: {list(self._tools.keys())}")
        return self._tools[name]

    def list_all(self) -> list[Tool]:
        """列出所有已注册的工具"""
        return list(self._tools.values())

    def to_api_schema(self) -> list[dict]:
        """转为 LLM API 兼容的 tool definitions 格式

        输出格式兼容 OpenAI 和 Anthropic API。
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]