"""GXCode ChatArea Widget

基于 Collapsible 的可折叠对话展示区。
工具调用和思考过程默认收起，Focus + Enter/Space 切换展开/折叠。
"""

from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Static


class _ToolBlock(Collapsible):
    """可折叠的工具调用块 —— 标题带执行状态，内容内置 Static"""

    def __init__(self, name: str, args_str: str):
        self.args_str = args_str
        self._tool_name = name
        self._content = Static(f"[dim]参数: {args_str}[/]")
        # 内容作为 children 传入，让 Collapsible 自己渲染标题 + 内容
        super().__init__(
            self._content,
            title=f"[bold yellow][工具][/] [bold]{name}[/] [dim]执行中...[/]",
            collapsed_symbol="○",
            expanded_symbol="●",
        )

    def set_result(self, output: str, ok: bool = True) -> None:
        preview = output[:500] + ("..." if len(output) > 500 else "")
        if ok:
            self.title = f"[bold yellow][工具][/] [bold]{self._tool_name}[/] [bold green]✓ 成功[/]"
            self._content.update(
                f"[dim]参数: {self.args_str}[/]\n"
                f"[green]结果:[/] {preview}"
            )
        else:
            self.title = f"[bold yellow][工具][/] [bold]{self._tool_name}[/] [bold red]✗ 失败[/]"
            self._content.update(
                f"[dim]参数: {self.args_str}[/]\n"
                f"[red]错误:[/] {preview}"
            )


class _ThinkingBlock(Collapsible):
    """可折叠的思考过程块"""

    def __init__(self):
        self._thinking = Static("")
        super().__init__(
            self._thinking,
            title="[dim italic]思考中...[/]",
            collapsed_symbol="○",
            expanded_symbol="●",
        )

    @property
    def thinking_widget(self) -> Static:
        return self._thinking


class ChatArea(VerticalScroll):
    """对话消息展示区 —— 基于 Widget 动态布局"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 流式文本状态
        self._thinking_block: _ThinkingBlock | None = None
        self._thinking_text: str = ""
        self._assistant_widget: Static | None = None
        self._assistant_text: str = ""
        # 最近一个工具块
        self._last_tool_block: _ToolBlock | None = None

    # ── 内部 ──

    def _mount(self, widget) -> None:
        self.mount(widget)
        self.scroll_end(animate=False)

    # ── 欢迎 / 清空 ──

    def add_welcome(self) -> None:
        self._mount(Static(
            "[bold magenta]GXCode[/] — 命令行 AI 编程助手\n\n"
            "[bold]快速开始[/]\n"
            "  [bold]/help[/]       查看全部命令\n"
            "  [bold]/plan[/]       规划模式（只读分析）\n"
            "  [bold]/do[/]         执行模式（全工具）\n"
            "  [bold]/permission[/] 切换权限模式\n\n"
            "[dim]直接输入消息开始对话 · Ctrl+C 退出[/]"
        ))

    def clear(self) -> None:
        self.remove_children()

    # ── 非折叠 ──

    def add_user_message(self, text: str) -> None:
        self._reset_streams()
        self._mount(Static(f"[bold cyan]▸ 你[/]", classes="role-user"))
        self._mount(Static(text, classes="user-msg"))

    def add_info(self, message: str) -> None:
        self._mount(Static(message))

    def add_iteration_marker(self, iteration: int, max_iterations: int) -> None:
        self._mount(Static(f"[dim italic]─ 迭代 {iteration}/{max_iterations} ─[/]", classes="iter-marker"))

    def add_error(self, message: str) -> None:
        preview = message[:500] + ("..." if len(message) > 500 else "")
        self._mount(Static(f"[bold red]错误:[/] {preview}", classes="error-msg"))

    # ── AI 输出 ──

    def start_assistant_message(self) -> None:
        self._reset_streams()
        self._assistant_text = ""
        self._mount(Static("[bold green]● GXCode[/]", classes="role-ai"))
        self._assistant_widget = Static("", classes="assistant-msg")
        self.mount(self._assistant_widget)

    # ── 思考 ──

    def start_thinking_message(self) -> None:
        self._reset_streams()
        self._thinking_text = ""
        self._thinking_block = _ThinkingBlock()
        self._mount(self._thinking_block)

    # ── 流式追加 ──

    def append_current(self, text: str) -> None:
        if self._assistant_widget is not None:
            self._assistant_text += text
            self._assistant_widget.update(self._assistant_text)
        elif self._thinking_block is not None:
            self._thinking_text += text
            self._thinking_block.thinking_widget.update(self._thinking_text)
        self.scroll_end(animate=False)

    # ── 工具调用 ──

    def add_tool_call(self, name: str, args: dict) -> None:
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self._last_tool_block = _ToolBlock(name, args_str)
        self._mount(self._last_tool_block)

    def add_tool_result(self, output: str, ok: bool = True) -> None:
        if self._last_tool_block is not None:
            self._last_tool_block.set_result(output, ok)
        self.scroll_end(animate=False)

    # ── 重置 ──

    def _reset_streams(self) -> None:
        self._assistant_widget = None
        self._assistant_text = ""
        self._thinking_block = None
        self._thinking_text = ""
        self._last_tool_block = None
