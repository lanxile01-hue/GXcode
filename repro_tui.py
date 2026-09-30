"""Textual 无头测试：把第 5 轮的 5 个工具调用 + 真实结果喂给 ChatArea，看是否崩溃。"""

import asyncio
import sys
from pathlib import Path

ROOT = Path("D:/agent/Mewagent")
sys.path.insert(0, str(ROOT / "src"))

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input

from gxcode.tui.chat_area import ChatArea

FILES = [
    ("glob_find", {"pattern": "src/gxcode/commands/builtin/*.py"}, None),
    ("read_file", {"path": "src/gxcode/permission/checker.py"}, "src/gxcode/permission/checker.py"),
    ("read_file", {"path": "src/gxcode/tools/file_tools.py"}, "src/gxcode/tools/file_tools.py"),
    ("read_file", {"path": "src/gxcode/context/manager.py"}, "src/gxcode/context/manager.py"),
    ("read_file", {"path": "src/gxcode/memory/context_builder.py"}, "src/gxcode/memory/context_builder.py"),
]


class T(App):
    def __init__(self):
        super().__init__()
        self.error = None

    def compose(self) -> ComposeResult:
        yield Container(ChatArea(id="chat-area"))

    def on_mount(self) -> None:
        asyncio.create_task(self._drive())

    async def _drive(self):
        chat = self.query_one("#chat-area", ChatArea)
        try:
            chat.add_user_message("讲一下整个项目")
            chat.add_iteration_marker(5, 25)
            chat.start_assistant_message()
            chat.append_current("我把剩余的模块目录和工具、权限层的细节补上。")
            for name, args, path in FILES:
                chat.add_tool_call(name, args)
            for name, args, path in FILES:
                if path is None:
                    out = "\n".join(str(p.relative_to(ROOT)) for p in ROOT.glob("src/gxcode/commands/builtin/*.py"))
                else:
                    out = (ROOT / path).read_text(encoding="utf-8")
                chat.add_tool_result(out, ok=True)
                print(f"rendered result for {path or 'glob'} OK, len={len(out)}")
            print("ALL RENDERED WITHOUT EXCEPTION")
        except Exception as e:
            import traceback
            self.error = e
            print(f"!!! TUI EXCEPTION: {type(e).__name__}: {e}")
            traceback.print_exc()
        self.exit()


async def main():
    app = T()
    async with app.run_test() as pilot:
        await pilot.pause(0.5)
    print("error captured:", app.error)

asyncio.run(main())
