"""GXCode 命令分流器

在用户输入入口判断：斜杠开头走命令分发，否则送 Agent。
命令未命中带 /help 引导。
"""

from gxcode.commands.controller import UIController
from gxcode.commands.parser import parse_command
from gxcode.commands.registry import CommandRegistry


async def dispatch(
    text: str,
    registry: CommandRegistry,
    controller: UIController,
    agent_handler,  # async callable(text) -> None
) -> bool:
    """分流并执行命令

    Args:
        text: 用户原始输入
        registry: 命令注册中心
        controller: 界面控制接口
        agent_handler: Agent 入口（异步函数，接收文本）

    Returns:
        True 表示已处理（命令或错误），False 表示应送 Agent
    """
    name, args = parse_command(text)

    # 非命令 → Agent
    if name is None:
        return False

    # 空命令名 → 显示提示
    if not name:
        controller.add_message("[dim]/help 查看所有命令[/]")
        return True

    # 查找命令
    cmd = registry.find(name)
    if cmd is None:
        controller.add_message(f"[bold red]未知命令:[/] /{name}\n[dim]输入 /help 查看可用命令[/]")
        return True

    # 执行
    try:
        result = cmd.handler(args, controller) if cmd.handler else None
    except Exception as e:
        controller.add_message(f"[bold red]命令执行失败:[/] {e}")
        return True

    # prompt 模式：把结果作为用户消息送入 Agent
    if cmd.type == "prompt" and result:
        await agent_handler(result)

    return True