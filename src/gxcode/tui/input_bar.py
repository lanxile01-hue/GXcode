"""GXCode InputBar Widget

底部输入栏，基于 Textual Input。
支持回车提交、发送期间禁用、Tab 补全命令。
"""

from textual.widgets import Input


class InputBar(Input):
    """底部输入栏 — 回车提交，Tab 补全"""

    BINDINGS = [
        ("tab", "complete", "补全命令"),
    ]

    def __init__(self, completions_callback=None, **kwargs):
        super().__init__(
            placeholder="输入消息，Enter 发送（Tab 补全命令）...",
            **kwargs,
        )
        # completions_callback(text) -> list[str] (补全候选项) or (text, completions) -> str|None (应用补全)
        self._completions_callback = completions_callback
        self._completions: list[str] = []
        self._completion_index = 0
        self._original_text = ""

    def set_completions_callback(self, callback) -> None:
        self._completions_callback = callback

    def action_complete(self) -> None:
        """Tab 键处理：单匹配直补，多匹配弹菜单"""
        if not self._completions_callback:
            return

        text = self.value
        if not text.startswith("/"):
            return

        from gxcode.commands.completion import get_completions, apply_completion, format_menu

        completions = get_completions(text, self._completions_callback())
        if not completions:
            return

        if len(completions) == 1:
            # 单匹配直接补全
            self.value = completions[0] + " "
            self.cursor_position = len(self.value)
            return

        # 多匹配：先找公共前缀
        from gxcode.commands.completion import _common_prefix
        common = _common_prefix(completions)
        if common and len(common) > len(text):
            self.value = common
            self.cursor_position = len(self.value)
        else:
            # 弹菜单提示
            self.notify(format_menu(completions), title="补全", timeout=3)