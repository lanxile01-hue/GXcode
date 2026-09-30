"""GXCode 记忆上下文构建

在请求处理前组装记忆上下文：
1. 三层项目指令
2. 项目级记忆索引
3. 用户级记忆索引

拼接后注入 system prompt，让 Agent 启动时已「读过」记忆。
"""

from pathlib import Path

from gxcode.memory.instructions import load_instructions


def build_memory_context(project_root: Path) -> str:
    """组装记忆上下文

    Args:
        project_root: 项目根目录

    Returns:
        拼接后的 Markdown 文本，可直接注入 system prompt
    """
    parts: list[str] = []

    # 1. 项目指令（三层）
    instructions = load_instructions(project_root)
    if instructions:
        parts.append(instructions)

    # 2. 项目级记忆索引
    project_index_path = project_root / ".gxcode" / "memory" / "index.md"
    project_index = _read_if_exists(project_index_path)
    if project_index:
        parts.append(project_index)

    # 3. 用户级记忆索引
    user_index_path = Path.home() / ".gxcode" / "memory" / "index.md"
    user_index = _read_if_exists(user_index_path)
    if user_index:
        parts.append(user_index)

    return "\n\n".join(parts)


def _read_if_exists(path: Path) -> str:
    """读取文件内容，不存在返回空"""
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""