"""GXCode 工具系统

提供统一的工具接口、注册中心和六个内置工具。
"""

from gxcode.tools.base import Tool, ToolResult
from gxcode.tools.registry import ToolRegistry
from gxcode.tools.file_tools import ReadFileTool, WriteFileTool, EditFileTool
from gxcode.tools.system_tools import RunCommandTool, GlobFindTool, GrepSearchTool


def create_default_registry() -> ToolRegistry:
    """创建包含六个默认工具的工具注册中心"""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(RunCommandTool())
    registry.register(GlobFindTool())
    registry.register(GrepSearchTool())
    return registry


__all__ = [
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "RunCommandTool",
    "GlobFindTool",
    "GrepSearchTool",
    "create_default_registry",
]