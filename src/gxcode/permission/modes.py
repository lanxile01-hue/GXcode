"""GXCode 权限模式枚举"""

from enum import Enum


class PermissionMode(Enum):
    STRICT = "strict"          # 只读放行，写操作需确认
    DEFAULT = "default"        # 按规则判断，未命中走人在回路
    PERMISSIVE = "permissive"  # 除黑名单外全部放行
    CUSTOM = "custom"          # 完全按自定义规则