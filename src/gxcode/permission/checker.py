"""GXCode 权限检查器 — 五层防御编排

黑名单 → 沙箱 → 权限模式 → 规则引擎 → 人在回路
"""

from dataclasses import dataclass, field

from gxcode.permission.blacklist import check_command
from gxcode.permission.modes import PermissionMode
from gxcode.permission.rules import Rule, RuleEngine
from gxcode.permission.sandbox import check_path


@dataclass
class CheckResult:
    """权限检查结果"""
    allowed: bool
    reason: str
    requires_confirm: bool = False  # 需要人在回路确认
    tool_name: str = ""             # 待确认的工具名（人在回路用）
    params: dict = field(default_factory=dict)  # 待确认的工具参数


class PermissionChecker:
    """五层防御权限检查器"""

    READ_TOOLS = {"read_file", "glob_find", "grep_search"}

    # 层2 沙箱覆盖的文件操作工具（按 path 参数做目录限制）
    PATH_TOOLS = {"read_file", "write_file", "edit_file"}

    def __init__(
        self,
        mode: PermissionMode = PermissionMode.DEFAULT,
        project_root: str = ".",
    ):
        self.mode = mode
        self.project_root = project_root
        self.engine = RuleEngine(project_root)

    def set_mode(self, mode: PermissionMode) -> None:
        """运行时切换权限模式（供 /permission 命令调用）"""
        self.mode = mode

    def check(self, tool_name: str, **params) -> CheckResult:
        """五层防御判断

        返回 CheckResult，allowed=False 时 Agent 不执行工具但继续运行；
        requires_confirm=True 时需经人在回路确认后才执行。
        """

        # 层 1: 黑名单（仅 run_command）
        if tool_name == "run_command":
            command = params.get("command", "")
            allowed, reason = check_command(command)
            if not allowed:
                return CheckResult(allowed=False, reason=reason)

        # 层 2: 沙箱（文件操作工具）
        if tool_name in self.PATH_TOOLS:
            path = params.get("path", "")
            if path:
                allowed, reason = check_path(path, self.project_root)
                if not allowed:
                    return CheckResult(allowed=False, reason=reason)

        # 层 3: 权限模式
        if self.mode == PermissionMode.PERMISSIVE:
            # 除黑名单和沙箱外全部放行
            return CheckResult(allowed=True, reason="permissive 模式")

        if self.mode == PermissionMode.STRICT:
            # 只读工具直接放行；写操作与未知工具需确认
            if tool_name in self.READ_TOOLS:
                return CheckResult(allowed=True, reason="strict 模式只读放行")
            return CheckResult(
                allowed=True, reason="strict 模式需确认",
                requires_confirm=True,
                tool_name=tool_name, params=params,
            )

        # 层 4: 规则引擎
        result = self.engine.match(tool_name, **params)
        if result is True:
            return CheckResult(allowed=True, reason="规则允许")
        if result is False:
            return CheckResult(allowed=False, reason="规则拦截")

        # 层 5: 人在回路
        if self.mode == PermissionMode.CUSTOM:
            # CUSTOM 模式：规则未命中时默认拒绝（fail-closed）
            return CheckResult(allowed=False, reason="custom 模式：无匹配规则，已拒绝")

        if self.mode in (PermissionMode.DEFAULT, PermissionMode.STRICT):
            # 只读工具默认放行；非只读工具需确认
            if tool_name in self.READ_TOOLS:
                return CheckResult(allowed=True, reason="只读工具放行")
            return CheckResult(
                allowed=True, reason="需要用户确认",
                requires_confirm=True,
                tool_name=tool_name, params=params,
            )

        return CheckResult(allowed=True, reason="放行")
