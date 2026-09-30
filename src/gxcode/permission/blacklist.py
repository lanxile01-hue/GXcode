"""GXCode 高危命令黑名单

不可配置的正则列表，在命令执行前硬拦截。
"""

import re

# 高危命令正则（不可配置）
# 注意：run_command 走 shell，命令最终由 shell 解析，这里只能做字符串层面的底线拦截。
_DENY_PATTERNS: list[tuple[str, str]] = [
    # (正则, 描述)
    # rm 递归强制删除：覆盖 -rf / -fr / -r -f / -f -r 及带 --recursive --force 的变体
    (r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*|-[a-z]*f\s+-[a-z]*r[a-z]*|-[a-z]*r\s+-[a-z]*f[a-z]*)\s+/(?:\s|$)", "禁止递归强制删除根目录"),
    (r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*|-[a-z]*f\s+-[a-z]*r[a-z]*|-[a-z]*r\s+-[a-z]*f[a-z]*)\s+~(?:\s|$)", "禁止递归强制删除家目录"),
    (r"\brm\s+(--recursive\s+--force|--force\s+--recursive|-R\s+-f|-f\s+-R)\s+/(?:\s|$)", "禁止递归强制删除根目录"),
    (r"\brm\s+(--recursive\s+--force|--force\s+--recursive|-R\s+-f|-f\s+-R)\s+~(?:\s|$)", "禁止递归强制删除家目录"),
    (r"\brm\s+.*\s--no-preserve-root\b", "禁止绕过 rm 根目录保护"),
    (r"\bmkfs\.", "禁止格式化文件系统"),
    (r"\bdd\s+if=", "禁止磁盘直接读写"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "禁止 fork 炸弹"),
    (r"\bchmod\s+777\s+/", "禁止更改根目录权限为 777"),
    (r">\s*/dev/sd[a-z]", "禁止直接写入磁盘设备"),
    (r"\bshutdown\b", "禁止关机命令"),
    (r"\breboot\b", "禁止重启命令"),
    (r"\bwget\s+.*\|\s*sh\b", "禁止直接执行下载脚本"),
    (r"\bcurl\s+.*\|\s*sh\b", "禁止直接执行下载脚本"),
]


def check_command(command: str) -> tuple[bool, str]:
    """检查命令是否命中黑名单

    Returns:
        (allowed, reason) — allowed=False 表示被拦截
    """
    for pattern, description in _DENY_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"高危命令被拦截: {description}"
    return True, ""