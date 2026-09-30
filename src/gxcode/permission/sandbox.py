"""GXCode 路径沙箱

限制文件操作只能在项目根目录内。
先解析符号链接再做前缀判断。
"""

from pathlib import Path


def check_path(path_str: str, project_root: str) -> tuple[bool, str]:
    """检查路径是否在项目根目录内

    先 resolve() 解析符号链接，再做前缀判断。

    Returns:
        (allowed, reason)
    """
    try:
        root = Path(project_root).resolve()
        target = (root / path_str).resolve()
    except (OSError, ValueError) as e:
        return False, f"路径解析失败: {e}"

    # 前缀判断
    try:
        target.relative_to(root)
    except ValueError:
        return False, f"路径越权: {path_str} 不在项目目录 {root} 内"

    return True, ""