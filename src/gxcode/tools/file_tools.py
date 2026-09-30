"""GXCode 文件操作工具

read_file: 读取文件内容
write_file: 创建或覆盖写入文件
edit_file: 查找替换文件中的文本（唯一匹配）
"""

from pathlib import Path

from gxcode.tools.base import Tool, ToolResult


def _resolve_safe(path: str) -> Path:
    """安全解析路径，拒绝 .. 越权"""
    cwd = Path.cwd().resolve()
    resolved = (cwd / path).resolve()
    if not str(resolved).startswith(str(cwd)):
        raise ValueError(f"路径越权，不允许访问工作目录之外: {path}")
    return resolved


class ReadFileTool(Tool):
    name = "read_file"
    description = "读取文件内容。用于查看现有代码、配置、文档等。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径（相对或绝对，相对于工作目录）",
            },
        },
        "required": ["path"],
    }

    async def execute(self, path: str) -> ToolResult:
        try:
            target = _resolve_safe(path)
        except ValueError as e:
            return ToolResult.fail(str(e))

        try:
            content = target.read_text(encoding="utf-8")
            return ToolResult.ok(content)
        except FileNotFoundError:
            return ToolResult.fail(f"文件不存在: {path}")
        except Exception as e:
            return ToolResult.fail(f"读取文件失败: {e}")


class WriteFileTool(Tool):
    name = "write_file"
    is_safe = False
    description = "创建或覆盖写入文件。父目录不存在时自动创建。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径（相对或绝对）",
            },
            "content": {
                "type": "string",
                "description": "要写入的文件内容",
            },
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str) -> ToolResult:
        try:
            target = _resolve_safe(path)
        except ValueError as e:
            return ToolResult.fail(str(e))

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult.ok(f"文件已写入: {path} ({len(content)} 字符)")
        except Exception as e:
            return ToolResult.fail(f"写入文件失败: {e}")


class EditFileTool(Tool):
    name = "edit_file"
    is_safe = False
    description = (
        "在文件中查找并替换文本。必须先 read_file 确认当前内容。"
        "old_string 必须在文件中唯一出现一次，否则报错让模型调整。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径",
            },
            "old_string": {
                "type": "string",
                "description": "要替换的原文，必须在文件中唯一匹配",
            },
            "new_string": {
                "type": "string",
                "description": "替换后的新文本",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(
        self, path: str, old_string: str, new_string: str
    ) -> ToolResult:
        try:
            target = _resolve_safe(path)
        except ValueError as e:
            return ToolResult.fail(str(e))

        try:
            content = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ToolResult.fail(f"文件不存在: {path}")
        except Exception as e:
            return ToolResult.fail(f"读取文件失败: {e}")

        count = content.count(old_string)
        if count == 0:
            return ToolResult.fail(
                f"未找到匹配文本。请检查 old_string 是否正确，"
                f"注意空格和缩进必须精确匹配。"
            )
        if count > 1:
            return ToolResult.fail(
                f"匹配到 {count} 处相同文本，请缩小匹配范围使其唯一。"
                f"可以在 old_string 中包含更多上下文（前后行）来精确定位。"
            )

        new_content = content.replace(old_string, new_string, 1)
        try:
            target.write_text(new_content, encoding="utf-8")
            return ToolResult.ok(f"文件已修改: {path}（替换 1 处）")
        except Exception as e:
            return ToolResult.fail(f"写入文件失败: {e}")