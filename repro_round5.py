"""复现脚本：重放 20260930-114329-bc2d 会话的第 5 轮，定位循环提前结束的原因。

思路：
1. 从 .gxcode/sessions/20260930-114329-bc2d.jsonl 重建真实历史（到第 15 行为止，
   即第 5 轮 LLM 调用之前的状态）。
2. 用 ScriptedProvider 在第 5 轮返回与会话日志第 16 行完全一致的
   文本 + 5 个工具调用。
3. 之后 Provider 返回一段普通文本（模拟模型继续），
   观察循环是否在第 5 轮中断、以什么 reason 结束。
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path("D:/agent/Mewagent")
sys.path.insert(0, str(ROOT / "src"))

from gxcode.agent.loop import AgentLoop
from gxcode.context import ContextManager, Summarizer, TokenCounter
from gxcode.permission import PermissionChecker, PermissionMode
from gxcode.session import ChatSession
from gxcode.tools import ToolRegistry
from gxcode.tools.file_tools import EditFileTool, ReadFileTool, WriteFileTool
from gxcode.tools.system_tools import GlobFindTool, GrepSearchTool, RunCommandTool
from gxcode.types_ import Message, TextDelta, ToolCall

SESSION_LOG = ROOT / ".gxcode" / "sessions" / "20260930-114329-bc2d.jsonl"

# 第 5 轮真实的模型输出（来自日志第 16 行）
TURN5_TEXT = "我把剩余的模块目录和工具、权限层的细节补上。"
TURN5_CALLS = [
    ToolCall(tool_id="", name="glob_find", arguments={"pattern": "src/gxcode/commands/builtin/*.py"}),
    ToolCall(tool_id="", name="read_file", arguments={"path": "src/gxcode/permission/checker.py"}),
    ToolCall(tool_id="", name="read_file", arguments={"path": "src/gxcode/tools/file_tools.py"}),
    ToolCall(tool_id="", name="read_file", arguments={"path": "src/gxcode/context/manager.py"}),
    ToolCall(tool_id="", name="read_file", arguments={"path": "src/gxcode/memory/context_builder.py"}),
]


class ScriptedProvider:
    """按轮次脚本化回放，第 1 轮返回第 5 轮的内容（因为历史已重建到第 4 轮末）"""

    def __init__(self):
        self.calls = 0

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        print(f"\n>>> [ScriptedProvider] LLM call #{self.calls}, history={len(messages)} msgs", flush=True)
        if self.calls == 1:
            yield TextDelta(content=TURN5_TEXT)
            for tc in TURN5_CALLS:
                yield tc
        else:
            yield TextDelta(content="（模拟模型继续）这是第六轮的普通回复。")


def rebuild_history():
    """从 JSONL 日志重建 Message 列表（第 1..15 行）"""
    history = []
    lines = SESSION_LOG.read_text(encoding="utf-8").splitlines()
    for line in lines[:15]:  # 前 15 行 = 第 5 轮 LLM 调用前的完整历史
        e = json.loads(line)
        role = e.get("role")
        if role == "tool_result":
            content = f"[tool_result from {e.get('tool')}]\\n{e.get('content', '')}"
            history.append(Message(role="user", content=content.replace("\\n", "\n")))
        elif role in ("user", "assistant"):
            history.append(Message(role=role, content=e.get("content", "")))
    return history


async def main():
    history = rebuild_history()
    print(f"rebuilt history: {len(history)} messages")

    provider = ScriptedProvider()
    session = ChatSession(provider, "fake-model", system_prompt="You are GXCode.")
    session._history = list(history)

    registry = ToolRegistry()
    for t in (ReadFileTool(), WriteFileTool(), EditFileTool(),
              GlobFindTool(), GrepSearchTool(), RunCommandTool()):
        registry.register(t)

    permission = PermissionChecker(mode=PermissionMode.DEFAULT, project_root=str(ROOT))

    # 真实 ContextManager（用不会触网的假 summarizer）
    class FakeSummaryProvider:
        async def stream_chat(self, messages, model, **options):
            yield TextDelta(content="压缩摘要（假）")

    from gxcode.config import ContextConfig
    ctx_mgr = ContextManager(
        session=session,
        counter=TokenCounter(),
        summarizer=Summarizer(provider=FakeSummaryProvider(), model="fake"),
        config=ContextConfig(),
    )

    loop = AgentLoop(
        session, registry,
        max_iterations=25,
        permission_checker=permission,
        context_manager=ctx_mgr,
    )

    # 注意：历史已包含用户消息，这里传空消息避免重复注入（run 会再 add_user_message，
    # 真实场景里这是第 5 轮，循环从第 1 轮重新计数不影响工具执行路径）
    try:
        async for event in loop.run("（已重放，继续第 5 轮）"):
            etype = type(event).__name__
            detail = ""
            if etype == "ToolResultEvent":
                out = (event.output or event.error or "")[:80].replace("\n", " | ")
                detail = f" ok={event.error is None} out={out}"
            elif etype == "LoopFinished":
                detail = f" reason={event.reason!r} iterations={event.iterations} summary={str(event.summary)[:200]!r}"
            elif etype == "IterationStart":
                detail = f" iter={event.iteration}/{event.max_iterations}"
            elif etype == "ErrorEvent":
                detail = f" msg={event.message[:200]}"
            print(f"[EVENT] {etype}{detail}", flush=True)
    except Exception as e:
        import traceback
        print(f"\n!!! 消费侧异常: {type(e).__name__}: {e}")
        traceback.print_exc()

    print("\n--- 最终历史长度:", len(session._history))
    print("--- 末尾 3 条:")
    for m in session._history[-3:]:
        print(f"  [{m.role}] {m.content[:100].replace(chr(10), ' | ')}")


asyncio.run(main())
