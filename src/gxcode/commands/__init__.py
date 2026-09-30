"""GXCode Commands 包 — 命令注册与分发"""

from gxcode.commands.registry import Command, CommandRegistry
from gxcode.commands.parser import parse_command
from gxcode.commands.controller import UIController
from gxcode.commands.dispatcher import dispatch
from gxcode.commands.builtin import register_all

__all__ = [
    "Command",
    "CommandRegistry",
    "parse_command",
    "UIController",
    "dispatch",
    "register_all",
]