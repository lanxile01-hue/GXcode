"""GXCode 命令解析器

识别 / 前缀，第一个空格前是命令名（转小写），之后是参数字符串。
空输入返回 None，未命中返回 ("", "")。
"""


def parse_command(text: str) -> tuple[str | None, str]:
    """解析斜杠命令

    Args:
        text: 原始输入文本

    Returns:
        (command_name, args) — command_name 为 None 表示非命令
    """
    text = text.strip()
    if not text:
        return None, ""

    if not text.startswith("/"):
        return None, text

    # 去掉 / 前缀
    rest = text[1:].strip()
    if not rest:
        return "", ""

    # 第一个空格分割命令名和参数
    parts = rest.split(maxsplit=1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return name, args