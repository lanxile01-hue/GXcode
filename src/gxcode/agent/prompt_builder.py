"""GXCode PromptBuilder

按优先级组装模块化的 System Prompt。
固定模块 7 个 + 环境信息，模块间空行分隔。
"""

import os
import platform

from gxcode.tools.base import Tool


def _identity() -> str:
    return "你是 GXCode，一个命令行 AI 编程助手。你能读写文件、执行命令、搜索代码，帮助用户完成编程任务。"

def _constraints() -> str:
    return """## 系统约束
- 只能访问当前工作目录及其子目录，不允许越权访问
- 不要执行危险命令（如 rm -rf /、格式化磁盘等）
- 不要修改系统配置文件"""

def _task_mode(mode: str) -> str:
    if mode == "plan":
        return """## 任务模式：Plan Mode
你处于规划模式，只能使用只读工具。分析任务需求，阅读代码，制定计划。不要修改任何文件。"""
    return ""

def _action_rules() -> str:
    return """## 动作执行规则
- 修改文件前必须先 read_file 确认当前内容
- 优先使用专用工具（如 read_file、edit_file）而非 run_command
- 一次只做一个改动，确认结果后再进行下一步

## 回复形式规则（重要）
- 需要继续调查或修改时，必须在**同一轮回复内直接调用工具**，不要只输出"让我看看…""接下来…""我先…"这类不做事的旁白
- 纯文本回复等同于宣告任务结束。只有当任务已完成、并已给出完整可交付的最终答案时，才输出纯文本
- 如果目标尚未达成，就不要输出纯文本，务必继续调用工具"""


def _env_info(env: dict) -> str:
    """环境信息模块。

    env 未显式传入时回落到真实运行环境，避免模型不知道自己在哪个平台上
    （历史问题：模型在 Windows 上尝试 `ls` 而失败）。
    """
    system = env.get("os") or platform.system()
    cwd = env.get("cwd") or os.getcwd()
    if env.get("shell"):
        shell = env["shell"]
    elif os.name == "nt":
        shell = os.environ.get("COMSPEC", "cmd.exe")
    else:
        shell = os.environ.get("SHELL", "sh")

    parts = [
        "## 环境信息",
        f"- 操作系统: {system}",
        f"- 工作目录: {cwd}",
        f"- Shell: {shell}",
    ]
    if os.name == "nt":
        parts.append(
            "- 命令提示: 当前是 Windows 环境，run_command 走 cmd.exe，"
            "请使用 dir / type / findstr / where 等命令，"
            "不要使用 ls / cat / grep / which（会报「不是内部或外部命令」）"
        )
    else:
        parts.append(
            "- 命令提示: 当前是 Unix 风格环境，可使用 ls / cat / grep 等命令"
        )
    parts.append(
        "- 查找文件请优先用 glob_find，搜索文件内容请优先用 grep_search，"
        "不要用 run_command 代替这两个工具"
    )
    return "\n".join(parts)

def _tool_usage(tools: list[Tool]) -> str:
    lines = ["## 可用工具"]
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
    return "\n".join(lines)

def _tone_style() -> str:
    return "## 语气风格\n简洁、直接、不废话。用中文回复。"

def _output_format() -> str:
    return """## 文本输出格式
- 代码块使用 ``` 包裹，标注语言
- 文件路径使用反引号包裹如 `src/main.py`"""


class PromptBuilder:
    """模块化 System Prompt 构建器"""

    def __init__(self):
        self._modules: list[tuple[str, int, callable]] = [
            ("identity", 1, _identity),
            ("constraints", 2, _constraints),
            ("task_mode", 3, lambda: _task_mode(self._mode)),
            ("action_rules", 4, _action_rules),
            ("tool_usage", 5, lambda: _tool_usage(self._tools)),
            ("tone_style", 6, _tone_style),
            ("output_format", 7, _output_format),
        ]
        self._mode = "act"
        self._tools: list[Tool] = []

    def add_module(self, name: str, content_fn: callable, priority: int) -> None:
        """注册新模块"""
        self._modules.append((name, priority, content_fn))

    def build(self, mode: str = "act", tools: list[Tool] | None = None, **env) -> str:
        """按优先级组装完整 System Prompt"""
        self._mode = mode
        self._tools = tools or []

        # 按优先级排序
        sorted_modules = sorted(self._modules, key=lambda m: m[1])

        # 环境信息紧跟在身份模块之后：模型要先知道自己在哪个平台、有哪些工具
        parts: list[str] = []
        env_block = _env_info(env)
        env_inserted = False
        for name, _, fn in sorted_modules:
            content = fn()
            if not content:  # 空模块跳过
                continue
            parts.append(content)
            if name == "identity":
                parts.append(env_block)
                env_inserted = True
        if not env_inserted:
            parts.insert(0, env_block)

        return "\n\n".join(parts)