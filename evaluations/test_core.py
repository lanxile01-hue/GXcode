"""Deterministic regression/evaluation tests for GXCode core components.

These tests do not call a real LLM. They exercise the safety, persistence,
context-management and agent-orchestration contracts that can be measured
locally and repeated in CI.
"""
import asyncio
import json
import os
import time
from pathlib import Path

from gxcode.agent.loop import AgentLoop
from gxcode.context.file_spill import spill_files
from gxcode.context.manager import ContextManager
from gxcode.context.summarizer import Summarizer
from gxcode.context.token_counter import TokenCounter
from gxcode.config import ContextConfig
from gxcode.memory.session_store import SessionStore
from gxcode.permission.checker import PermissionChecker
from gxcode.permission.modes import PermissionMode
from gxcode.permission.rules import Rule
from gxcode.mcp.adapter import MCPToolWrapper
from gxcode.tools.base import Tool, ToolResult
from gxcode.tools.registry import ToolRegistry
from gxcode.types_ import ContinuationNudge, Message, TextDelta, ToolCall


class EchoTool(Tool):
    name = "echo"
    description = "echo"
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}}
    is_safe = True

    async def execute(self, text=""):
        return ToolResult.ok(f"echo:{text}")


class FakeProvider:
    """First asks for echo, then returns a final answer."""
    def __init__(self):
        self.calls = 0

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        if self.calls == 1:
            yield ToolCall(tool_id="1", name="echo", arguments={"text": "ok"})
        else:
            yield TextDelta(content="done")


class ChainProvider:
    def __init__(self): self.calls = 0
    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        if self.calls == 1:
            yield ToolCall("1", "echo", {"text": "a"})
        elif self.calls == 2:
            yield ToolCall("2", "echo", {"text": "b"})
        else:
            yield TextDelta("chain-complete")


class SummaryProvider:
    def __init__(self, fail=False): self.calls = 0; self.fail = fail
    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        if self.fail: raise RuntimeError("summary failure")
        yield TextDelta("TASK: preserved summary")


class FakeMcpClient:
    def __init__(self): self.calls = []
    async def call_tool(self, name, args):
        self.calls.append((name, args)); return {"content": [{"type": "text", "text": "remote-ok"}]}


def test_permission_blocks_dangerous_command(tmp_path):
    checker = PermissionChecker(PermissionMode.DEFAULT, str(tmp_path))
    result = checker.check("run_command", command="rm -rf /")
    assert not result.allowed


def test_permission_blocks_path_escape(tmp_path):
    checker = PermissionChecker(PermissionMode.DEFAULT, str(tmp_path))
    result = checker.check("read_file", path="../outside.txt")
    assert not result.allowed


def test_spill_preserves_preview_and_disk_copy(tmp_path):
    payload = "x" * 9000
    messages = [Message("user", "[tool_result from read_file]\n" + payload)]
    result = spill_files(messages, tmp_path, single_threshold=100, batch_threshold=200)
    assert len(result.spilled_paths) == 1
    assert Path(result.spilled_paths[0]).read_text(encoding="utf-8") == payload
    assert "read_file" in result.messages[0].content
    assert len(result.messages[0].content) < len(messages[0].content)


def test_session_store_round_trip_and_bad_line_recovery(tmp_path):
    store = SessionStore(tmp_path)
    sid = store.create()
    store.append(sid, {"role": "user", "content": "hello"})
    (tmp_path / f"{sid}.jsonl").open("a", encoding="utf-8").write("not-json\n")
    entries = store.read(sid)
    assert len(entries) == 1 and entries[0]["content"] == "hello"
    assert store.list_sessions()[0].message_count == 2


def test_agent_loop_executes_tool_then_finishes():
    async def run():
        provider = FakeProvider()
        # Minimal session object avoids network/configuration.
        from gxcode.session import ChatSession
        session = ChatSession(provider, "fake", system_prompt="system")
        registry = ToolRegistry(); registry.register(EchoTool())
        events = [e async for e in AgentLoop(session, registry).run("hello")]
        return provider, events, session

    provider, events, session = asyncio.run(run())
    assert provider.calls == 2
    assert any(getattr(e, "output", "") == "echo:ok" for e in events)
    assert events[-1].reason == "finished"
    assert session.history[-1].content == "done"


def test_agent_loop_supports_multi_iteration_chain():
    async def run():
        from gxcode.session import ChatSession
        p = ChainProvider(); s = ChatSession(p, "fake")
        r = ToolRegistry(); r.register(EchoTool())
        events = [e async for e in AgentLoop(s, r, max_iterations=5).run("chain")]
        return p, events, s
    p, events, s = asyncio.run(run())
    assert p.calls == 3
    assert sum(1 for e in events if hasattr(e, "output") and e.output) == 2
    assert events[-1].summary == "chain-complete"


def test_safe_tools_run_concurrently():
    class Slow(EchoTool):
        name = "slow"
        async def execute(self, **kwargs):
            await asyncio.sleep(.05); return ToolResult.ok("ok")
    async def run():
        from gxcode.session import ChatSession
        class P:
            async def stream_chat(self, messages, model, **opts):
                if not hasattr(self, "n"): self.n = 0
                self.n += 1
                if self.n == 1:
                    yield ToolCall("1", "slow", {}); yield ToolCall("2", "slow", {})
                else: yield TextDelta("done")
        p=P(); s=ChatSession(p,"x"); r=ToolRegistry(); r.register(Slow())
        start=time.perf_counter(); [e async for e in AgentLoop(s,r).run("x")]
        return time.perf_counter()-start
    assert asyncio.run(run()) < .16


def test_permission_session_rule_overrides_default(tmp_path):
    checker = PermissionChecker(PermissionMode.DEFAULT, str(tmp_path))
    checker.engine.add_session_rule(Rule("run_command", "echo *", True))
    result = checker.check("run_command", command="echo hello")
    assert result.allowed and not result.requires_confirm


def test_context_compression_preserves_user_messages_and_boundary(tmp_path):
    provider = SummaryProvider()
    from gxcode.session import ChatSession
    session = ChatSession(provider, "x")
    history = [Message("user", "user requirement")]
    history += [Message("assistant", "old implementation " * 20)] * 4
    history += [Message("user", "recent request")]
    session.replace_history(history)
    cfg = ContextConfig(window_size=20, auto_margin=0, keep_tokens=5, keep_min=2, spill_dir=str(tmp_path))
    mgr = ContextManager(session, TokenCounter(), Summarizer(provider, "x"), cfg)
    result = asyncio.run(mgr.check_and_compress_async())
    assert result.success
    assert any(m.content == "user requirement" for m in result.messages)
    assert any("璇蜂娇鐢" in m.content or "具体细节" in m.content for m in result.messages)


def test_summary_circuit_breaker_trips_after_failures():
    provider = SummaryProvider(fail=True)
    summarizer = Summarizer(provider, "x", max_failures=2)
    messages = [Message("assistant", "old " * 30)] * 6
    counter = TokenCounter()
    assert not asyncio.run(summarizer.compress(messages, counter, keep_tokens=2, keep_min=2)).success
    assert not asyncio.run(summarizer.compress(messages, counter, keep_tokens=2, keep_min=2)).success
    assert summarizer.tripped
    assert provider.calls == 2


def test_token_anchor_incremental_estimate_and_invalidation():
    c = TokenCounter(); base=[Message("user", "abcd"), Message("assistant", "efgh")]
    from gxcode.types_ import TokenUsage
    c.set_anchor(base, TokenUsage(10, 2))
    assert c.estimate(base + [Message("user", "1234")]) == 13
    assert c.estimate([Message("user", "changed")]) == 1


def test_mcp_wrapper_normalizes_text_result():
    client=FakeMcpClient(); tool=MCPToolWrapper(client, {"name":"remote","description":"d","inputSchema":{"type":"object"}})
    result=asyncio.run(tool.execute(value=1))
    assert result.success and result.output == "remote-ok" and client.calls == [("remote", {"value":1})]


def test_skill_activation_substitutes_parameters():
    from gxcode.skills.loader import Skill
    from gxcode.skills.registry import SkillRegistry
    reg=SkillRegistry({"review": Skill("review", params=["file"], body="Review {{file}}")})
    active=reg.activate("review", "src/main.py")
    assert active and active.body == "Review src/main.py"


def test_command_parser_handles_case_and_args():
    from gxcode.commands.parser import parse_command
    assert parse_command(" /PLAN now ") == ("plan", "now")
    assert parse_command("plain text")[0] is None


# ── 回归：Agent 循环"空转"纠偏 ──
# 历史 bug：模型只回一句「让我再看看主要目录的代码结构。」却没有发出 tool_calls，
# loop 把它当成最终回答直接 return（reason=finished），任务在第 4 轮静默中断。


class _StallThenWorkProvider:
    """第 1 轮只说前摇旁白，第 2 轮才真正调用工具，第 3 轮给最终答案"""

    def __init__(self):
        self.calls = 0

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        if self.calls == 1:
            yield TextDelta("让我再看看主要目录的代码结构。")
        elif self.calls == 2:
            yield ToolCall("1", "echo", {"text": "ok"})
        else:
            yield TextDelta("项目概况：这是一个命令行 AI 编程助手。" * 4)


class _AlwaysStallProvider:
    """每轮都只输出前摇旁白，永不调用工具"""

    def __init__(self):
        self.calls = 0

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        yield TextDelta("让我先看一下文件。")


def test_loop_nudges_stalled_preamble_instead_of_finishing():
    async def run():
        from gxcode.session import ChatSession
        p = _StallThenWorkProvider()
        s = ChatSession(p, "fake", system_prompt="system")
        r = ToolRegistry(); r.register(EchoTool())
        events = [e async for e in AgentLoop(s, r).run("explain")]
        return p, events, s

    p, events, s = asyncio.run(run())
    assert p.calls == 3, f"纠偏后应继续迭代，实际只调用了 {p.calls} 次"
    assert sum(1 for e in events if isinstance(e, ContinuationNudge)) == 1
    assert events[-1].reason == "finished"
    # 原生格式：assistant 的 tool_calls 必须以 tool_calls 字段写入历史
    # （不再拼 "[调用工具]" 文本摘要 —— 那正是模型模仿着伪造调用的样板）
    assert any(
        m.role == "assistant" and m.tool_calls
        for m in s.history
    ), "assistant 的 tool_calls 必须以原生字段写入历史"


def test_loop_preamble_nudge_is_bounded_and_never_hangs():
    async def run():
        from gxcode.session import ChatSession
        p = _AlwaysStallProvider()
        s = ChatSession(p, "fake", system_prompt="system")
        r = ToolRegistry(); r.register(EchoTool())
        return p, [e async for e in AgentLoop(s, r).run("x")]

    p, events = asyncio.run(run())
    assert sum(1 for e in events if isinstance(e, ContinuationNudge)) == 2, "纠偏次数必须封顶"
    assert events[-1].reason == "finished"
    assert p.calls < 10, "空转纠偏不得导致无限迭代"


def test_loop_plain_text_finish_is_not_nudged():
    """真正的最终答案（不含前摇词、文本较长）不应被纠偏打断"""
    async def run():
        from gxcode.session import ChatSession
        p = FakeProvider()
        s = ChatSession(p, "fake", system_prompt="system")
        r = ToolRegistry(); r.register(EchoTool())
        return p, [e async for e in AgentLoop(s, r).run("hello")]

    p, events = asyncio.run(run())
    assert not any(isinstance(e, ContinuationNudge) for e in events)
    assert events[-1].reason == "finished"


def test_run_command_output_decoded_with_system_encoding():
    """Windows cmd 输出 GBK，固定用 utf-8 解会变乱码"""
    from gxcode.tools.system_tools import _decode_output
    zh = "“ls”不是内部或外部命令，也不是可运行的程序"
    assert _decode_output(zh.encode("gbk")) == zh
    assert _decode_output("hello 世界".encode("utf-8")) == "hello 世界"
    assert _decode_output(b"") == ""


def test_system_prompt_enforces_same_turn_tool_call_and_reports_env():
    from gxcode.agent import build_act_prompt
    r = ToolRegistry(); r.register(EchoTool())
    prompt = build_act_prompt(r.list_all())
    assert "同一轮回复内直接调用工具" in prompt
    assert "纯文本回复等同于宣告任务结束" in prompt
    assert "## 环境信息" in prompt and "操作系统:" in prompt
    if os.name == "nt":
        assert "不要使用 ls" in prompt, "Windows 上必须提示不要用 ls/cat/grep"


# ── 回归：真实会话里出现过的空转句与短结论句 ──


class _OneShotProvider:
    """第一轮输出给定文本，之后固定输出最终答案"""

    def __init__(self, first: str, final: str):
        self.calls = 0
        self._first = first
        self._final = final

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        yield TextDelta(self._first if self.calls == 1 else self._final)


async def _run_loop(provider):
    from gxcode.session import ChatSession
    s = ChatSession(provider, "fake", system_prompt="system")
    r = ToolRegistry(); r.register(EchoTool())
    return s, [e async for e in AgentLoop(s, r).run("q")]


def test_loop_nudges_real_world_stall_sentence():
    """原句：溢写文件又被溢写了一次。我直接用命令读取原文件内容。

    它不含「让我/接下来」这类词，旧词表会漏判，必须靠「我直接」+动作对象兜住。
    """
    p = _OneShotProvider(
        "溢写文件又被溢写了一次。我直接用命令读取原文件内容。",
        "## GXCode 项目全貌\n\n这是一个用 Python 写的命令行 AI 编程助手。" * 3,
    )
    _, events = asyncio.run(_run_loop(p))
    assert sum(1 for e in events if isinstance(e, ContinuationNudge)) == 1
    assert p.calls == 2
    assert events[-1].reason == "finished"


def test_loop_short_conclusion_is_not_nudged():
    """短但有结论词的回答属于正常交付，不能被误判成空转"""
    p = _OneShotProvider("已修复，文件已保存。", "unused")
    _, events = asyncio.run(_run_loop(p))
    assert not any(isinstance(e, ContinuationNudge) for e in events)
    assert p.calls == 1 and events[-1].reason == "finished"


def test_spill_does_not_recurse_on_rereading_spilled_content(tmp_path):
    """溢写 → 整文件重读 → 再溢写 的套娃必须被拦截"""
    payload = "y" * 9000
    seen: set[str] = set()
    msg = [Message("user", "[tool_result from read_file]\n" + payload)]

    first = spill_files(msg, tmp_path, single_threshold=100, batch_threshold=200,
                        spilled_hashes=seen)
    assert len(first.spilled_paths) == 1
    assert "不要用 read_file 整文件重读" in first.messages[0].content

    second = spill_files(msg, tmp_path, single_threshold=100, batch_threshold=200,
                         spilled_hashes=seen)
    assert second.spilled_paths == [], "同一份内容不得二次溢写"
    assert "不再重复溢写" in second.messages[0].content
    assert len(list(tmp_path.glob("*.txt"))) == 1, "磁盘上不得新增溢写文件"


def test_spill_default_thresholds_allow_normal_source_files(tmp_path):
    """默认阈值必须容得下常规源码文件，否则模型永远读不到完整文件"""
    cfg = ContextConfig()
    assert cfg.single_threshold >= 32_000
    assert cfg.batch_threshold >= 64_000
    src = "x" * 15_000  # 本项目 12~18KB 的源码文件量级
    result = spill_files(
        [Message("user", "[tool_result from read_file]\n" + src)],
        tmp_path,
        single_threshold=cfg.single_threshold,
        batch_threshold=cfg.batch_threshold,
    )
    assert result.spilled_paths == [], "常规源码文件不该被溢写"


# ── 回归：伪工具调用（模型把调用写成文本而不走 function calling）──
# 历史 bug：deepseek-chat 在第 5 轮输出 286 字的 "[调用工具] glob_find(...)" 纯文本，
# 循环的 `not turn.tool_calls → finished` 把它误判为任务完成，任务静默中断。


class _FakeTextCallProvider:
    """第 1 轮把工具调用写成文本，第 2 轮真正调用，第 3 轮给最终答案"""

    def __init__(self):
        self.calls = 0

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        if self.calls == 1:
            yield TextDelta(
                "我把剩余的模块目录和工具、权限层的细节补上。\n"
                "[调用工具] glob_find(pattern='src/**/*.py')；"
                "read_file(path='src/gxcode/main.py')"
            )
        elif self.calls == 2:
            yield ToolCall("1", "echo", {"text": "ok"})
        else:
            yield TextDelta("## 项目全貌\n这是完整的最终答案。" * 5)


class _AlwaysFakeTextCallProvider:
    """每轮都把工具调用写成文本，从不真正调用"""

    def __init__(self):
        self.calls = 0

    async def stream_chat(self, messages, model, **options):
        self.calls += 1
        yield TextDelta(
            "我继续查看更多模块的实现细节来补全项目全貌信息。"
            "[调用工具] read_file(path='src/gxcode/main.py')；"
            "read_file(path='src/gxcode/session.py')；"
            "read_file(path='src/gxcode/agent/loop.py')"
        )


def test_loop_nudges_fake_text_tool_calls_instead_of_finishing():
    async def run():
        from gxcode.session import ChatSession
        p = _FakeTextCallProvider()
        s = ChatSession(p, "fake", system_prompt="system")
        r = ToolRegistry(); r.register(EchoTool())
        return p, [e async for e in AgentLoop(s, r).run("讲一下整个项目")]

    p, events = asyncio.run(run())
    assert p.calls == 3, f"伪调用纠偏后应继续迭代，实际只调用了 {p.calls} 次"
    assert sum(1 for e in events if isinstance(e, ContinuationNudge)) == 1
    assert events[-1].reason == "finished"


def test_loop_fake_text_nudge_is_bounded():
    async def run():
        from gxcode.session import ChatSession
        p = _AlwaysFakeTextCallProvider()
        s = ChatSession(p, "fake", system_prompt="system")
        r = ToolRegistry(); r.register(EchoTool())
        return p, [e async for e in AgentLoop(s, r).run("x")]

    p, events = asyncio.run(run())
    assert sum(1 for e in events if isinstance(e, ContinuationNudge)) == 2, "伪调用纠偏必须封顶"
    assert events[-1].reason == "finished"
    assert p.calls < 10, "伪调用纠偏不得导致无限迭代"


def test_loop_normal_answer_with_code_is_not_fake_call():
    """最终答案里含普通代码（如函数定义）不应被误判为伪工具调用"""
    class _CodeAnswerProvider:
        def __init__(self): self.calls = 0

        async def stream_chat(self, messages, model, **options):
            self.calls += 1
            yield TextDelta(
                "## 项目说明\n\n```python\n"
                "def not_a_tool(some_arg=1):\n    return some_arg\n```\n以上。"
            )

    async def run():
        from gxcode.session import ChatSession
        p = _CodeAnswerProvider()
        s = ChatSession(p, "fake", system_prompt="system")
        r = ToolRegistry(); r.register(EchoTool())
        return p, [e async for e in AgentLoop(s, r).run("q")]

    p, events = asyncio.run(run())
    assert not any(isinstance(e, ContinuationNudge) for e in events)
    assert p.calls == 1 and events[-1].reason == "finished"


# ── 回归：OpenAI 协议原生 tool_calls 序列化 ──


def test_openai_serialization_native_tool_calls_and_pairing():
    from gxcode.provider.openai import _to_api_messages

    native_calls = [{
        "id": "call_1", "type": "function",
        "function": {"name": "read_file", "arguments": "{\"path\": \"a.py\"}"},
    }]
    history = [
        Message("system", "sys"),
        Message("user", "q"),
        Message("assistant", "我看一下", tool_calls=native_calls),
        Message("tool", "文件内容", tool_call_id="call_1", name="read_file"),
        Message("assistant", "完成"),
    ]
    out = _to_api_messages(history)
    assert out[2]["tool_calls"] == native_calls
    assert out[2]["content"] == "我看一下"
    assert out[3] == {"role": "tool", "tool_call_id": "call_1", "content": "文件内容"}
    assert out[4] == {"role": "assistant", "content": "完成"}


def test_openai_serialization_orphan_tool_result_downgrades():
    """孤儿工具结果（配对的 assistant 不在历史里）必须降级为 user 文本，避免 API 400"""
    from gxcode.provider.openai import _to_api_messages

    out = _to_api_messages([
        Message("user", "q"),
        Message("tool", "结果", tool_call_id="call_missing", name="read_file"),
    ])
    assert out[1]["role"] == "user"
    assert "[tool_result from read_file]" in out[1]["content"]


def test_openai_serialization_fills_missing_tool_responses():
    """assistant.tool_calls 后缺少响应时自动合成占位，保证配对完整"""
    from gxcode.provider.openai import _to_api_messages

    native_calls = [{
        "id": "call_1", "type": "function",
        "function": {"name": "echo", "arguments": "{}"},
    }]
    out = _to_api_messages([
        Message("user", "q"),
        Message("assistant", "", tool_calls=native_calls),
        Message("user", "继续"),
    ])
    # assistant(tool_calls) → 合成的 tool 响应 → user
    assert out[1]["tool_calls"] == native_calls
    assert out[2]["role"] == "tool" and out[2]["tool_call_id"] == "call_1"
    assert out[3]["role"] == "user"


def test_spill_preserves_tool_call_id_for_native_tool_messages(tmp_path):
    """原生 role="tool" 消息溢写后必须保留 tool_call_id（维持 OpenAI 配对）"""
    payload = "z" * 9000
    messages = [Message("tool", payload, tool_call_id="call_9", name="read_file")]
    result = spill_files(messages, tmp_path, single_threshold=100, batch_threshold=200)
    assert len(result.spilled_paths) == 1
    m = result.messages[0]
    assert m.role == "tool" and m.tool_call_id == "call_9" and m.name == "read_file"
    assert "read_file" in m.content
    assert len(m.content) < len(payload)
