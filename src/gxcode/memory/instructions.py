"""GXCode 项目指令加载

三层路径加载 Markdown 指令，支持 @include 递归引用：
- {project_root}/INSTRUCTIONS.md        最高优先级
- {project_root}/.gxcode/instructions.md
- ~/.gxcode/instructions.md             最低优先级（用户全局）

@include 防环路（visited 集合）、限嵌套深度、路径沙箱。
"""

from pathlib import Path

_MAX_INCLUDE_DEPTH = 3


def load_instructions(project_root: Path, max_depth: int = _MAX_INCLUDE_DEPTH) -> str:
    """加载三层项目指令，拼接为一段 Markdown

    高优先级排在前面，让模型优先遵循。
    文件不存在时静默跳过。
    """
    sections: list[str] = []

    # 层 1：项目根（最高优先级）
    root_file = project_root / "INSTRUCTIONS.md"
    if root_file.is_file():
        sections.append(_load_with_includes(root_file, project_root, max_depth))

    # 层 2：项目 .gxcode/
    gxcode_file = project_root / ".gxcode" / "instructions.md"
    if gxcode_file.is_file():
        sections.append(_load_with_includes(gxcode_file, project_root, max_depth))

    # 层 3：用户全局（最低优先级）
    user_file = Path.home() / ".gxcode" / "instructions.md"
    if user_file.is_file():
        sections.append(_load_with_includes(user_file, project_root, max_depth))

    return "\n\n---\n\n".join(sections)


def _load_with_includes(
    file_path: Path,
    project_root: Path,
    max_depth: int,
    visited: set[str] | None = None,
    depth: int = 0,
) -> str:
    """读取 Markdown 文件，递归解析 @include 指令"""
    if visited is None:
        visited = set()

    resolved = file_path.resolve()
    key = str(resolved)

    # 防环路
    if key in visited:
        return f"[@include 循环引用已跳过: {file_path}]"

    # 路径沙箱
    project_root_resolved = str(project_root.resolve())
    if not key.startswith(project_root_resolved):
        return f"[@include 路径越界已跳过: {file_path}]"

    # 嵌套深度
    if depth >= max_depth:
        return f"[@include 超过最大嵌套深度 {max_depth}: {file_path}]"

    visited.add(key)
    content = resolved.read_text(encoding="utf-8")

    result_lines: list[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("@include "):
            rel_path = stripped[len("@include "):].strip()
            abs_path = (resolved.parent / rel_path).resolve()
            included = _load_with_includes(
                abs_path, project_root, max_depth, visited, depth + 1,
            )
            result_lines.append(included)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)