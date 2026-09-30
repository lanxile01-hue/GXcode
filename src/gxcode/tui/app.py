"""GXCode Textual App

顶层应用，组装 ChatArea + InputBar + 底部状态栏，
编排 AgentLoop 的流式事件到 UI 渲染。
"""

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Header, Input, Static

from gxcode.agent import AgentLoop, build_act_prompt, build_plan_prompt
from gxcode.commands import CommandRegistry, UIController, dispatch, register_all
from gxcode.permission.modes import PermissionMode
from gxcode.session import ChatSession
from gxcode.tools import ToolRegistry
from gxcode.tui.chat_area import ChatArea
from gxcode.tui.confirm_screen import ConfirmScreen
from gxcode.tui.input_bar import InputBar
from gxcode.types_ import (
    CompressEvent,
    ContinuationNudge,
    ErrorEvent,
    IterationStart,
    LoopFinished,
    SpillEvent,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    ToolResultEvent,
    UsageEvent,
)

CSS = """
Screen {
    background: $surface;
}

Header {
    background: $panel;
    color: $foreground;
    text-style: bold;
}

/* 底部状态栏 */
#status-bar {
    height: 1;
    background: $panel;
    color: $text-muted;
    padding: 0 2;
}

/* 聊天区 */
#chat-area {
    height: 1fr;
    border: none;
    padding: 1 2 0 2;
    scrollbar-size: 1 1;
}

/* 消息角色标识 */
.role-user {
    margin-top: 1;
}

.role-ai {
    margin-top: 1;
}

/* 消息内容块：左侧色条区分角色 */
.user-msg {
    border-left: thick $accent;
    padding: 0 1;
    margin: 0 0 1 0;
}

.assistant-msg {
    border-left: thick $success;
    padding: 0 1;
    margin: 0 0 1 0;
}

.error-msg {
    color: $text-error;
    margin-bottom: 1;
}

.iter-marker {
    color: $text-muted;
    margin: 1 0;
}

/* 输入栏 */
#input-bar {
    height: 3;
    margin: 0 1 0 1;
    background: $boost;
    border: tall $primary;
}

#input-bar:focus {
    border: tall $accent;
}
"""


class StatusBar(Static):
    """底部状态栏 — 常驻显示模式、权限、Token 用量和快捷键提示"""

    mode: reactive[str] = reactive("act")
    perm: reactive[str] = reactive("default")
    prompt: reactive[int] = reactive(0)
    completion: reactive[int] = reactive(0)

    def render(self) -> str:
        if self.mode == "plan":
            mode_badge = "[bold yellow]● PLAN[/]"
        else:
            mode_badge = "[bold green]● ACT[/]"
        total = self.prompt + self.completion
        return (
            f"{mode_badge}  [dim]│[/]  "
            f"权限 [bold]{self.perm}[/]  [dim]│[/]  "
            f"Token [bold]{total:,}[/]  [dim]│[/]  "
            f"[dim]⏎ 发送 · Tab 补全 · Ctrl+C 退出[/]"
        )

    def set_state(
        self,
        mode: str | None = None,
        perm: str | None = None,
        prompt: int | None = None,
        completion: int | None = None,
    ) -> None:
        """局部更新状态并重绘"""
        if mode is not None:
            self.mode = mode
        if perm is not None:
            self.perm = perm
        if prompt is not None:
            self.prompt = prompt
        if completion is not None:
            self.completion = completion


class GXCodeApp(App):
    """GXCode TUI 应用"""

    TITLE = "GXCode"
    SUB_TITLE = "终端 AI 编程助手"

    CSS = CSS

    BINDINGS = [
        ("ctrl+c", "request_quit", "退出"),
    ]

    def __init__(self, session: ChatSession, registry: ToolRegistry, permission_checker=None, context_manager=None, note_writer=None, skill_registry=None):
        super().__init__()
        self._session = session
        self._tool_registry = registry
        self._sending = False
        self._quit_pending = False
        self._mode = "act"
        self._permission = permission_checker
        self._permission_mode = "default"
        self._ctx_mgr = context_manager
        self._note_writer = note_writer
        self._total_prompt = 0
        self._total_completion = 0
        self._cmd_registry = CommandRegistry()
        register_all(self._cmd_registry)
        if skill_registry:
            _register_skill_commands(self._cmd_registry, skill_registry)
        self._ctrl = _AppController(self)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="⚡")
        yield Container(
            ChatArea(id="chat-area"),
            InputBar(id="input-bar"),
            StatusBar(id="status-bar"),
        )

    def on_mount(self) -> None:
        inp = self.query_one("#input-bar", InputBar)
        inp.focus()
        inp.set_completions_callback(lambda: self._cmd_registry)
        inp.placeholder = self._placeholder_for_mode()
        chat = self.query_one("#chat-area", ChatArea)
        chat.add_welcome()
        self._refresh_status()

    # ── 状态栏 ──

    def _refresh_status(self) -> None:
        bar = self.query_one("#status-bar", StatusBar)
        bar.set_state(
            mode=self._mode,
            perm=self._permission_mode,
            prompt=self._total_prompt,
            completion=self._total_completion,
        )

    def _placeholder_for_mode(self) -> str:
        if self._mode == "plan":
            return "Plan 模式：只读分析（输入 /do 切换执行）..."
        return "输入消息，Enter 发送（Tab 补全命令）..."

    # ── 退出 ──

    def action_request_quit(self) -> None:
        if self._quit_pending:
            self.exit()
        else:
            self._quit_pending = True
            chat = self.query_one("#chat-area", ChatArea)
            chat.add_info("[dim]再按一次 Ctrl+C 退出[/]")
            self.set_timer(3.0, self._reset_quit_pending)

    def _reset_quit_pending(self) -> None:
        self._quit_pending = False

    # ── 输入处理 ──

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._sending:
            return

        text = event.value.strip()
        if not text:
            return

        event.input.clear()
        chat = self.query_one("#chat-area", ChatArea)

        # 命令分发
        if text.startswith("/"):
            asyncio.create_task(dispatch(text, self._cmd_registry, self._ctrl, self._handle_input))
            return

        asyncio.create_task(self._handle_input(text))

    async def _handle_input(self, text: str) -> None:
        if self._sending:
            return

        self._sending = True
        chat = self.query_one("#chat-area", ChatArea)
        inp = self.query_one("#input-bar", InputBar)
        inp.disabled = True
        inp.placeholder = "思考中..."

        try:
            # 构建 AgentLoop
            registry = self._get_active_registry()
            prompt = build_plan_prompt(registry.list_all()) if self._mode == "plan" else build_act_prompt(registry.list_all())
            self._session._system_prompt = prompt
            loop = AgentLoop(
                self._session, registry,
                max_iterations=25,
                permission_checker=self._permission,
                context_manager=self._ctx_mgr,
                confirm_callback=self._confirm_tool,
            )

            # 渲染用户消息
            chat.add_user_message(text)

            # Agent 循环
            in_text = False
            async for event in loop.run(text):
                if isinstance(event, IterationStart):
                    chat.add_iteration_marker(event.iteration, event.max_iterations)
                    in_text = False

                elif isinstance(event, TextDelta):
                    if not in_text:
                        chat.start_assistant_message()
                        in_text = True
                    chat.append_current(event.content)

                elif isinstance(event, ThinkingDelta):
                    if not in_text:
                        chat.start_thinking_message()
                        in_text = True
                    chat.append_current(event.content)

                elif isinstance(event, ToolCall):
                    in_text = False  # 工具调用打断流式文本
                    chat.add_tool_call(event.name, event.arguments)

                elif isinstance(event, ToolResultEvent):
                    if event.error:
                        chat.add_tool_result(event.error, ok=False)
                    else:
                        chat.add_tool_result(event.output, ok=True)

                elif isinstance(event, ContinuationNudge):
                    chat.add_info(
                        f"[dim cyan]─ 迭代 {event.iteration}：模型未调用工具，"
                        f"已提醒继续 ─[/]"
                    )

                elif isinstance(event, LoopFinished):
                    if event.reason == "cancelled":
                        chat.add_info("[dim yellow]已取消[/]")
                    elif event.reason == "max_iterations":
                        chat.add_info("[dim yellow]达到迭代上限[/]")
                    elif event.reason == "tool_error_loop":
                        chat.add_info("[dim yellow]连续工具错误，已停止[/]")
                    elif event.reason == "stream_error":
                        chat.add_error(f"流错误: {event.summary}")
                    elif event.reason == "finished":
                        if event.summary or in_text:
                            # 正常收尾也给出明确标记，避免看起来"莫名其妙就停了"
                            chat.add_info(
                                f"[dim green]─ 完成（迭代 {event.iterations}）─[/]"
                            )
                        else:
                            chat.add_info("[dim yellow]未收到响应[/]")
                    # 显示累计 token
                    if self._total_prompt or self._total_completion:
                        total = self._total_prompt + self._total_completion
                        chat.add_info(f"[dim]Token: 输入 {self._total_prompt} + 输出 {self._total_completion} = {total} total[/]")
                    self._total_prompt = 0
                    self._total_completion = 0
                    self._refresh_status()
                    # Agent 循环结束后异步更新笔记
                    if event.reason != "cancelled" and self._note_writer:
                        history_snapshot = self._session.history
                        async def _update_and_show():
                            try:
                                count = await self._note_writer.update(history_snapshot)
                                if count > 0:
                                    chat.add_info(f"[dim cyan][记忆][/] 已更新 {count} 条笔记")
                                else:
                                    chat.add_info("[dim][记忆][/] 无需更新")
                            except Exception as e:
                                chat.add_info(f"[dim yellow][记忆][/] 更新失败: {e}")
                        asyncio.create_task(_update_and_show())

                elif isinstance(event, ErrorEvent):
                    chat.add_error(event.message)

                elif isinstance(event, UsageEvent):
                    u = event.usage
                    self._total_prompt += u.prompt_tokens
                    self._total_completion += u.completion_tokens
                    self._refresh_status()

                elif isinstance(event, SpillEvent):
                    chat.add_info(f"[dim cyan][溢写][/] 工具结果已保存到 {event.path}")

                elif isinstance(event, CompressEvent):
                    chat.add_info(f"[dim cyan][压缩][/] {event.old_count} 条消息 -> {event.kept_count} 条")

        except Exception as e:
            chat.add_error(f"异常: {e}")

        finally:
            inp.disabled = False
            inp.placeholder = self._placeholder_for_mode()
            inp.focus()
            self._sending = False

    def _get_active_registry(self) -> ToolRegistry:
        """根据当前模式返回工具注册中心"""
        if self._mode == "plan":
            from gxcode.tools.file_tools import ReadFileTool
            from gxcode.tools.system_tools import GlobFindTool, GrepSearchTool
            r = ToolRegistry()
            r.register(ReadFileTool())
            r.register(GlobFindTool())
            r.register(GrepSearchTool())
            return r
        return self._tool_registry

    # ── UIController 实现 ──

    def add_message(self, text: str) -> None:
        chat = self.query_one("#chat-area", ChatArea)
        chat.add_info(text)

    def send_user_message(self, text: str) -> None:
        asyncio.create_task(self._handle_input(text))

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        inp = self.query_one("#input-bar", InputBar)
        inp.placeholder = self._placeholder_for_mode()
        self._refresh_status()

    def get_mode(self) -> str:
        return self._mode

    def set_permission_mode(self, mode: str) -> None:
        """切换权限模式（真实更新 PermissionChecker，不污染 plan/act）"""
        if mode not in ("strict", "default", "permissive", "custom"):
            return
        self._permission_mode = mode
        if self._permission is not None:
            self._permission.set_mode(PermissionMode(mode))
        self._refresh_status()

    def get_permission_mode(self) -> str:
        return self._permission_mode

    async def _confirm_tool(self, tool_name: str, params: dict, reason: str) -> bool:
        """人在回路确认回调 — 弹出确认弹窗，等待用户批准/拒绝"""
        screen = ConfirmScreen(tool_name, params, reason)

        # 注意：不能用 push_screen_wait —— 它内部走 push_screen(wait_for_dismiss=True)，
        # 要求必须在 Textual worker 中运行，而 AgentLoop 跑在普通 asyncio task 里，
        # 会抛 NoActiveWorker 并被上层静默吞掉，导致“点批准也变拒绝”。
        # 这里改用 push_screen + callback + future 的方式等待结果。
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()

        def _on_result(result: object) -> None:
            if not future.done():
                future.set_result(bool(result))

        self.push_screen(screen, callback=_on_result)
        return await future

    def get_token_usage(self) -> tuple[int, int]:
        return (self._total_prompt, self._total_completion)

    def refresh_status(self) -> None:
        self._refresh_status()

    def clear_chat(self) -> None:
        chat = self.query_one("#chat-area", ChatArea)
        chat.clear()

    def trigger_context_compression(self) -> None:
        if self._ctx_mgr:
            # 同步版检查，手动模式余量 3K
            self._ctx_mgr.check_and_compress(auto=False)

    def get_session_info(self) -> dict:
        return {
            "模式": self._mode,
            "Token 输入": str(self._total_prompt),
            "Token 输出": str(self._total_completion),
        }


def _register_skill_commands(cmd_registry: CommandRegistry, skill_registry) -> None:
    """为每个 Skill 注册斜杠命令"""
    from gxcode.commands.registry import Command as Cmd
    from gxcode.commands.controller import UIController as UI

    # /skill — 列出所有 Skill
    def list_handler(args: str, ctrl: UI) -> str | None:
        names = skill_registry.list_names()
        if not names:
            ctrl.add_message("[dim]没有可用的 Skill[/]")
            return None
        lines = ["[bold]可用 Skill:[/]"]
        for n in names:
            lines.append(f"  [bold]/{n}[/] — 激活 {n} Skill")
        lines.append("[dim]输入 /skill_name 激活[/]")
        ctrl.add_message("\n".join(lines))
        return None

    cmd_registry.register(Cmd(
        name="skill", aliases=["skills"],
        desc="列出所有可用 Skill",
        usage="/skill",
        type="local",
        handler=list_handler,
    ))

    for name in skill_registry.list_names():
        # 跳过与内置命令冲突的 Skill 名
        if cmd_registry.find(name):
            continue

        def make_handler(n: str, sr):
            def handler(args: str, ctrl: UI) -> str | None:
                skill = sr.activate(n, args)
                if not skill:
                    ctrl.add_message(f"[bold red]Skill '{n}' 激活失败[/]")
                    return None
                return skill.body
            return handler

        cmd_registry.register(Cmd(
            name=name,
            desc=f"激活 Skill: {name}",
            usage=f"/{name} [参数]",
            type="prompt",
            handler=make_handler(name, skill_registry),
        ))


class _AppController(UIController):
    """UIController 适配器 — 包装 GXCodeApp，避免元类冲突"""

    def __init__(self, app: GXCodeApp):
        self._app = app

    def add_message(self, text: str) -> None:
        self._app.add_message(text)

    def send_user_message(self, text: str) -> None:
        self._app.send_user_message(text)

    def set_mode(self, mode: str) -> None:
        self._app.set_mode(mode)

    def get_mode(self) -> str:
        return self._app.get_mode()

    def set_permission_mode(self, mode: str) -> None:
        self._app.set_permission_mode(mode)

    def get_permission_mode(self) -> str:
        return self._app.get_permission_mode()

    def get_token_usage(self) -> tuple[int, int]:
        return self._app.get_token_usage()

    def refresh_status(self) -> None:
        self._app.refresh_status()

    def clear_chat(self) -> None:
        self._app.clear_chat()

    def trigger_context_compression(self) -> None:
        self._app.trigger_context_compression()

    def get_session_info(self) -> dict:
        return self._app.get_session_info()
