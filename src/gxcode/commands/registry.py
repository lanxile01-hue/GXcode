"""GXCode 命令注册中心

管理 Command 元数据，register() 时检测别名冲突（跨命令 name/alias 唯一）。
冲突直接 sys.exit(1)，不等运行时再炸。
"""

import sys
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Command:
    """一条命令的元数据"""
    name: str
    aliases: list[str] = field(default_factory=list)
    desc: str = ""
    usage: str = ""
    type: str = "local"               # "local" | "ui" | "prompt"
    handler: Callable | None = None    # (args: str, ctrl: UIController) -> str | None
    param_hint: str = ""
    hidden: bool = False


class CommandRegistry:
    """命令注册中心 — 启动时注册，冲突 panic"""

    def __init__(self):
        self._by_name: dict[str, Command] = {}
        self._all_names: set[str] = set()  # name + all aliases

    def register(self, cmd: Command) -> None:
        """注册命令，冲突则 sys.exit(1)"""
        # 检查 name
        if cmd.name in self._all_names:
            print(f"命令冲突: '{cmd.name}' 已被占用", file=sys.stderr)
            sys.exit(1)

        # 检查 aliases
        for alias in cmd.aliases:
            if alias in self._all_names:
                print(f"别名冲突: '{alias}'（命令 '{cmd.name}'）已被占用", file=sys.stderr)
                sys.exit(1)

        self._by_name[cmd.name] = cmd
        self._all_names.add(cmd.name)
        for alias in cmd.aliases:
            self._all_names.add(alias)

    def find(self, name: str) -> Command | None:
        """按名称或别名查找命令"""
        # 精确匹配 name
        if name in self._by_name:
            return self._by_name[name]
        # 别名匹配
        for cmd in self._by_name.values():
            if name in cmd.aliases:
                return cmd
        return None

    def list_visible(self) -> list[Command]:
        """列出所有非隐藏命令"""
        return [c for c in self._by_name.values() if not c.hidden]

    def list_all(self) -> list[Command]:
        return list(self._by_name.values())