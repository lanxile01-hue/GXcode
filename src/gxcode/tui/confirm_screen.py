"""GXCode 权限确认弹窗

用于人在回路（层5）：工具需要用户确认时弹出，等待用户批准/拒绝。
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """权限确认弹窗 — dismiss(True) 批准，dismiss(False) 拒绝"""

    def __init__(self, tool_name: str, params: dict, reason: str):
        super().__init__()
        self._tool_name = tool_name
        self._params = params
        self._reason = reason

    def compose(self) -> ComposeResult:
        args_str = ", ".join(f"{k}={v!r}" for k, v in self._params.items())
        with Vertical(id="confirm-dialog"):
            yield Static("[bold yellow]⚠ 需要你的确认[/]", id="confirm-title")
            yield Static(
                f"[bold]工具:[/] {self._tool_name}\n"
                f"[dim]参数: {args_str}[/]\n"
                f"[dim]原因: {self._reason}[/]",
                id="confirm-body",
            )
            with Horizontal(id="confirm-buttons"):
                yield Button("批准执行", variant="success", id="confirm-approve")
                yield Button("拒绝", variant="error", id="confirm-deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-approve":
            self.dismiss(True)
        else:
            self.dismiss(False)
