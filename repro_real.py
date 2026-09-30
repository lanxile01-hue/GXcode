"""用真实 DeepSeek API + 真实工具栈，无头重放「讲一下整个项目」，捕获第 5 轮的实际异常。"""

import asyncio
import sys
import traceback
from pathlib import Path

ROOT = Path("D:/agent/Mewagent")
sys.path.insert(0, str(ROOT / "src"))

from gxcode.agent.loop import AgentLoop
from gxcode.config import load_config, get_active
from gxcode.context import ContextManager, Summarizer, TokenCounter
from gxcode.permission import PermissionChecker, PermissionMode
from gxcode.provider import create_provider
from gxcode.session import ChatSession
from gxcode.tools import ToolRegistry
from gxcode.tools.file_tools import EditFileTool, ReadFileTool, WriteFileTool
from gxcode.tools.system_tools import GlobFindTool, GrepSearchTool, RunCommandTool
from gxcode.types_ import ErrorEvent, LoopFinished, ToolResultEvent


async def main():
    cfg = load_config(str(ROOT / "gxcode.yaml"))
    active = get_active(cfg)

    registry = ToolRegistry()
    for t in (ReadFileTool(), WriteFileTool(), EditFileTool(),
              GlobFindTool(), GrepSearchTool(), RunCommandTool()):
        registry.register(t)
    schema = registry.to_api_schema()

    provider = create_provider(active, tools=schema)
    summary_provider = create_provider(active, tools=None)

    from gxcode.agent import build_act_prompt
    session = ChatSession(provider=provider, model=active.model,
                          thinking=active.thinking,
                          system_prompt=build_act_prompt(registry.list_all()))

    ctx_mgr = ContextManager(
        session=session, counter=TokenCounter(),
        summarizer=Summarizer(provider=summary_provider, model=active.model),
        config=cfg.context,
    )
    permission = PermissionChecker(mode=PermissionMode.DEFAULT, project_root=str(ROOT))

    loop = AgentLoop(session, registry, max_iterations=25,
                     permission_checker=permission, context_manager=ctx_mgr)

    try:
        async for ev in loop.run("讲一下整个项目"):
            etype = type(ev).__name__
            if etype == "ToolResultEvent":
                out = (ev.output or ev.error or "")[:60].replace("\n", " | ")
                print(f"[EVENT] {etype} ok={ev.error is None} {out}", flush=True)
            elif etype == "LoopFinished":
                print(f"[EVENT] LoopFinished reason={ev.reason!r} iter={ev.iterations}\nsummary[:600]={str(ev.summary)[:600]!r}", flush=True)
            elif etype == "ErrorEvent":
                print(f"[EVENT] ErrorEvent {ev.message[:300]}", flush=True)
            elif etype in ("IterationStart",):
                print(f"[EVENT] IterationStart {ev.iteration}/{ev.max_iterations}", flush=True)
            else:
                print(f"[EVENT] {etype}", flush=True)
    except Exception as e:
        print(f"\n!!! 消费侧异常 {type(e).__name__}: {e}")
        traceback.print_exc()

    print("\nhistory len:", len(session._history))
    print("last msg:", session._history[-1].content[:200] if session._history else None)

asyncio.run(main())
