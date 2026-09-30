"""GXCode 系统工具

run_command: 执行 shell 命令
glob_find: 按 glob 模式查找文件
grep_search: 搜索文件内容（正则）
"""

import asyncio
import locale
import re
from pathlib import Path

from gxcode.tools.base import Tool, ToolResult


def _decode_output(data: bytes) -> str:
    """按候选编码解码子进程输出

    Windows cmd 输出的是 GBK(cp936)，固定用 utf-8 解会得到乱码
    （历史现象：`'ls' 不是内部或外部命令` 显示为 `'ls' ������...`）。
    utf-8 优先以兼容 Linux/macOS，失败后回落到本机首选编码 / GBK。
    """
    if not data:
        return ""
    candidates = ["utf-8", locale.getpreferredencoding(False) or "", "gbk", "mbcs"]
    tried: set[str] = set()
    for enc in candidates:
        if not enc or enc.lower() in tried:
            continue
        tried.add(enc.lower())
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


class RunCommandTool(Tool):
    name = "run_command"
    is_safe = False
    description = "在终端中执行一条 shell 命令，返回 stdout、stderr 和退出码。"
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
        },
        "required": ["command"],
    }

    async def execute(self, command: str) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=30.0
            )
            output_parts = []
            if stdout:
                output_parts.append(_decode_output(stdout))
            if stderr:
                output_parts.append(f"[stderr]\n{_decode_output(stderr)}")
            output_parts.append(f"[exit_code: {proc.returncode}]")
            return ToolResult.ok("\n".join(output_parts))
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            return ToolResult.fail(f"命令超时（30 秒）: {command}")
        except Exception as e:
            return ToolResult.fail(f"命令执行失败: {e}")


class GlobFindTool(Tool):
    name = "glob_find"
    description = "按 glob 模式查找文件，返回匹配的文件路径列表。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "glob 模式，如 '*.py'、'src/**/*.ts'",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str) -> ToolResult:
        try:
            cwd = Path.cwd()
            matches = list(cwd.glob(pattern))
            # 截断至 100 条
            if len(matches) > 100:
                shown = matches[:100]
                result = "\n".join(str(m.relative_to(cwd)) for m in shown)
                result += f"\n...（共 {len(matches)} 条，仅显示前 100 条）"
            elif matches:
                result = "\n".join(str(m.relative_to(cwd)) for m in matches)
            else:
                result = f"未找到匹配 '{pattern}' 的文件"
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(f"glob 查找失败: {e}")


class GrepSearchTool(Tool):
    name = "grep_search"
    description = "在文件中搜索匹配正则表达式的内容，返回匹配行及文件路径。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "正则表达式搜索模式",
            },
            "path": {
                "type": "string",
                "description": "搜索目录路径，默认当前目录",
                "default": ".",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            search_root = Path(path).resolve()
            if not search_root.exists():
                return ToolResult.fail(f"目录不存在: {path}")

            results: list[str] = []
            compiled = re.compile(pattern)
            max_results = 50

            for file_path in search_root.rglob("*"):
                if not file_path.is_file():
                    continue
                # 跳过二进制和隐藏文件
                if file_path.name.startswith("."):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, PermissionError):
                    continue

                for line_no, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        relative = file_path.relative_to(search_root)
                        results.append(f"{relative}:{line_no}: {line.strip()}")
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

            if results:
                output = "\n".join(results)
                if len(results) >= max_results:
                    output += f"\n...（截断至前 {max_results} 条）"
                return ToolResult.ok(output)
            else:
                return ToolResult.ok(f"未找到匹配 '{pattern}' 的内容")
        except re.error as e:
            return ToolResult.fail(f"正则表达式错误: {e}")
        except Exception as e:
            return ToolResult.fail(f"搜索失败: {e}")