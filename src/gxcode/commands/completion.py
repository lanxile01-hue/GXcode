"""GXCode 命令 Tab 补全

单匹配直接补全命令名，多匹配弹下拉菜单。
hidden=True 的命令不参与补全。
"""

from gxcode.commands.registry import CommandRegistry


def get_completions(text: str, registry: CommandRegistry) -> list[str]:
    """获取补全候选项

    Args:
        text: 当前输入框文本
        registry: 命令注册中心

    Returns:
        匹配的命令名列表（含 / 前缀）
    """
    if not text.startswith("/"):
        return []

    # 去掉 / 前缀，取已输入的部分
    partial = text[1:]
    # 只匹配命令名部分（忽略参数）
    name_part = partial.split()[0] if partial else ""
    name_lower = name_part.lower()

    matches: list[str] = []
    for cmd in registry.list_visible():
        if cmd.hidden:
            continue
        # 匹配 name
        if cmd.name.startswith(name_lower):
            matches.append(f"/{cmd.name}")
        # 匹配 aliases
        for alias in cmd.aliases:
            if alias.startswith(name_lower):
                matches.append(f"/{alias}")

    return sorted(matches)


def apply_completion(text: str, completions: list[str]) -> str | None:
    """应用补全

    Args:
        text: 当前输入框文本
        completions: 匹配列表

    Returns:
        补全后的文本（单匹配时），None 表示多匹配需弹菜单
    """
    if not completions:
        return None

    if len(completions) == 1:
        # 单匹配：直接补全并加空格
        return completions[0] + " "

    # 多匹配：找公共前缀
    common = _common_prefix(completions)
    if common and len(common) > len(text):
        # 可以补全到公共前缀
        return common

    return None  # 多匹配，弹菜单


def format_menu(completions: list[str]) -> str:
    """格式化补全菜单"""
    if not completions:
        return ""
    return "  ".join(completions)


def _common_prefix(strings: list[str]) -> str:
    """找字符串列表的公共前缀"""
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix