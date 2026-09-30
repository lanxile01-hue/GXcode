"""GXCode Skill 工具白名单 + load_skill 工具

- 白名单：限制当前可用工具集合，启动时验证工具存在
- load_skill：系统级工具，不受白名单限制，加载 Skill 完整指令
"""

import sys
from dataclasses import dataclass, field

from gxcode.skills.loader import Skill
from gxcode.skills.registry import SkillRegistry
from gxcode.tools.base import Tool, ToolResult


@dataclass
class WhitelistState:
    """白名单状态 — 记录原始工具列表，可恢复"""
    active: list[str] = field(default_factory=list)
    original: list[str] = field(default_factory=list)
    applied: bool = False


class ToolWhitelist:
    """工具白名单管理器"""

    def __init__(self, available_tools: list[str]):
        self._available = set(available_tools)
        self._state = WhitelistState()

    def validate(self, tools: list[str], skill_name: str) -> None:
        """验证白名单工具是否存在，不存在 panic"""
        for tool in tools:
            if tool not in self._available:
                print(
                    f"Skill '{skill_name}' 白名单包含不存在的工具 '{tool}'。"
                    f"可用工具: {sorted(self._available)}",
                    file=sys.stderr,
                )
                sys.exit(1)

    def apply(self, tools: list[str]) -> None:
        """应用白名单（为 Skill 激活时调用）"""
        if not self._state.applied:
            self._state.original = list(self._available)
            self._state.applied = True
        self._state.active = list(tools)

    def restore(self) -> None:
        """恢复完整工具列表"""
        self._state.active = []
        self._state.applied = False

    @property
    def active_tools(self) -> list[str]:
        if self._state.applied and self._state.active:
            return self._state.active
        return list(self._available)


class LoadSkillTool(Tool):
    """系统级 load_skill 工具 — 不受白名单限制"""

    name = "load_skill"
    description = "加载一个 Skill 的完整指令。参数: name (Skill名称), args (可选参数)"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill 名称"},
            "args": {"type": "string", "description": "可选参数"},
        },
        "required": ["name"],
    }
    is_safe = True

    def __init__(self, registry: SkillRegistry, whitelist: ToolWhitelist):
        super().__init__()
        self._registry = registry
        self._whitelist = whitelist

    async def execute(self, name: str, args: str = "") -> ToolResult:
        skill = self._registry.activate(name, args)
        if not skill:
            available = ", ".join(self._registry.list_names())
            return ToolResult.fail(f"Skill '{name}' 不存在。可用: {available}")

        # 应用白名单
        if skill.tools:
            self._whitelist.apply(skill.tools)

        return ToolResult.ok(
            f"Skill '{skill.name}' 已激活 ({skill.mode} 模式)。\n"
            f"工具白名单: {', '.join(skill.tools) if skill.tools else '全部'}\n\n"
            f"{skill.body}"
        )