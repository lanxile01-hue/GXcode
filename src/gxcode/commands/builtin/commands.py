"""GXCode 内置命令

10 个高频命令：help / compact / clear / plan / do / session / memory / permission / status / review
"""

from gxcode.commands.controller import UIController
from gxcode.commands.registry import Command, CommandRegistry


def register_all(registry: CommandRegistry) -> None:
    """注册所有内置命令"""
    _register_help(registry)
    _register_clear(registry)
    _register_compact(registry)
    _register_plan(registry)
    _register_do(registry)
    _register_session(registry)
    _register_memory(registry)
    _register_permission(registry)
    _register_status(registry)
    _register_review(registry)


# ── /help ──

def _register_help(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        if args.strip():
            # /help <命令名> → 显示单个命令详情
            cmd = r.find(args.strip().lower())
            if cmd:
                aliases = ", ".join(cmd.aliases) if cmd.aliases else "无"
                ctrl.add_message(
                    f"[bold]/ {cmd.name}[/]\n"
                    f"  描述: {cmd.desc}\n"
                    f"  用法: {cmd.usage}\n"
                    f"  别名: {aliases}\n"
                    f"  类型: {cmd.type}"
                )
            else:
                ctrl.add_message(f"[dim]未找到命令: /{args.strip()}[/]")
            return None
        # 列出所有命令
        lines = ["[bold]可用命令:[/]"]
        for cmd in r.list_visible():
            aliases_str = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"  [bold]/{cmd.name}[/]{aliases_str} — {cmd.desc}")
        ctrl.add_message("\n".join(lines))
        return None

    r.register(Command(
        name="help", aliases=["h", "?"],
        desc="显示帮助信息",
        usage="/help [命令名]",
        type="local",
        handler=handler,
        param_hint="[命令名]",
    ))


# ── /clear ──

def _register_clear(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        ctrl.clear_chat()
        return None

    r.register(Command(
        name="clear", aliases=["cls"],
        desc="清空聊天区域",
        usage="/clear",
        type="ui",
        handler=handler,
    ))


# ── /compact ──

def _register_compact(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        ctrl.trigger_context_compression()
        ctrl.add_message("[dim cyan]已触发上下文压缩[/]")
        return None

    r.register(Command(
        name="compact",
        desc="手动触发上下文压缩",
        usage="/compact",
        type="ui",
        handler=handler,
    ))


# ── /plan ──

def _register_plan(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        ctrl.set_mode("plan")
        ctrl.add_message("[bold yellow][Plan Mode][/] 只读分析模式，输入 /do 切换执行")
        return None

    r.register(Command(
        name="plan",
        desc="切换到计划模式（只读分析）",
        usage="/plan",
        type="ui",
        handler=handler,
    ))


# ── /do ──

def _register_do(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        ctrl.set_mode("act")
        ctrl.add_message("[bold green][Act Mode][/] 全工具就绪")
        return None

    r.register(Command(
        name="do", aliases=["act"],
        desc="切换到执行模式（全工具）",
        usage="/do",
        type="ui",
        handler=handler,
    ))


# ── /session ──

def _register_session(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        info = ctrl.get_session_info()
        lines = ["[bold]会话信息:[/]"]
        for k, v in info.items():
            lines.append(f"  {k}: {v}")
        ctrl.add_message("\n".join(lines))
        return None

    r.register(Command(
        name="session",
        desc="显示当前会话信息",
        usage="/session",
        type="local",
        handler=handler,
    ))


# ── /memory ──

def _register_memory(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        ctrl.add_message("[dim]记忆系统状态: 已加载指令和笔记索引[/]")
        return None

    r.register(Command(
        name="memory",
        desc="显示记忆状态",
        usage="/memory",
        type="local",
        handler=handler,
    ))


# ── /permission ──

def _register_permission(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        mode = args.strip().lower()
        if mode in ("strict", "default", "permissive", "custom"):
            ctrl.set_permission_mode(mode)
            ctrl.add_message(f"[bold][权限][/] 已切换为 {mode} 模式")
        else:
            current = ctrl.get_permission_mode()
            ctrl.add_message(
                f"[bold]权限模式（当前: {current}）:[/]\n"
                "  /permission strict — 写操作需确认\n"
                "  /permission default — 规则未命中时确认\n"
                "  /permission permissive — 除黑名单/沙箱外放行\n"
                "  /permission custom — 仅按规则，无匹配则拒绝"
            )
        return None

    r.register(Command(
        name="permission", aliases=["perm"],
        desc="显示或切换权限模式",
        usage="/permission [strict|default|permissive|custom]",
        type="ui",
        handler=handler,
        param_hint="[模式]",
    ))


# ── /status ──

def _register_status(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        prompt, completion = ctrl.get_token_usage()
        mode = ctrl.get_mode()
        ctrl.add_message(
            f"[bold]系统状态:[/]\n"
            f"  模式: {mode}\n"
            f"  Token: 输入 {prompt} + 输出 {completion} = {prompt + completion} total"
        )
        return None

    r.register(Command(
        name="status", aliases=["st"],
        desc="显示 token 用量和系统状态",
        usage="/status",
        type="local",
        handler=handler,
    ))


# ── /review ──

def _register_review(r: CommandRegistry) -> None:
    def handler(args: str, ctrl: UIController) -> str | None:
        target = args.strip() or "当前修改"
        return (
            f"请对以下内容进行代码审查（Code Review）：\n\n{target}\n\n"
            "请关注：\n"
            "1. 逻辑正确性\n"
            "2. 边界条件和错误处理\n"
            "3. 代码风格和可读性\n"
            "4. 性能和安全问题\n"
            "5. 是否有遗漏的测试用例"
        )

    r.register(Command(
        name="review", aliases=["cr"],
        desc="将代码审查提示词送入对话",
        usage="/review [目标描述]",
        type="prompt",
        handler=handler,
        param_hint="[目标]",
    ))