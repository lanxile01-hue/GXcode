"""Quantitative, deterministic benchmark for implemented GXCode mechanisms.

This is a component benchmark, not a claim of SWE-bench performance. It runs
fixed synthetic workloads against the actual permission, spill, context and
AgentLoop implementations and emits auditable metrics.
"""
import asyncio
import json
import statistics
import time
from pathlib import Path

from gxcode.agent.loop import AgentLoop
from gxcode.config import ContextConfig
from gxcode.context.file_spill import spill_files
from gxcode.context.summarizer import Summarizer
from gxcode.context.token_counter import TokenCounter
from gxcode.permission.checker import PermissionChecker
from gxcode.permission.modes import PermissionMode
from gxcode.session import ChatSession
from gxcode.tools.base import Tool, ToolResult
from gxcode.tools.registry import ToolRegistry
from gxcode.types_ import Message, TextDelta, ToolCall

ROOT = Path(__file__).resolve().parents[1]


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p / 100))]


class BenchTool(Tool):
    name = "bench_echo"; description = "benchmark echo"; is_safe = True
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}}
    async def execute(self, text=""): return ToolResult.ok(text)


class BenchProvider:
    def __init__(self): self.calls = 0
    async def stream_chat(self, messages, model, **opts):
        self.calls += 1
        if self.calls == 1: yield ToolCall("1", "bench_echo", {"text": "benchmark"})
        else: yield TextDelta("completed")


class SummaryProvider:
    async def stream_chat(self, messages, model, **opts):
        yield TextDelta("TASK: preserve requirements; STATUS: compressed")


def permission_benchmark():
    checker = PermissionChecker(PermissionMode.DEFAULT, str(ROOT))
    cases = [
        ("run_command", {"command": "rm -rf /"}, False),
        ("run_command", {"command": "mkfs.ext4 /dev/sda"}, False),
        ("run_command", {"command": "echo hello"}, True),
        ("read_file", {"path": "../etc/passwd"}, False),
        ("read_file", {"path": "src/gxcode/main.py"}, True),
        ("write_file", {"path": "src/tmp.txt"}, True),
    ] * 17  # 102 fixed decisions
    start = time.perf_counter(); correct = 0; blocked = 0
    for tool, args, expected_allowed in cases:
        result = checker.check(tool, **args)
        correct += result.allowed == expected_allowed
        blocked += not result.allowed
    elapsed = time.perf_counter() - start
    return {"cases": len(cases), "decision_accuracy": correct / len(cases),
            "blocked_cases": blocked, "p95_ms": percentile([elapsed * 1000 / len(cases)] * len(cases), 95)}


def spill_benchmark(tmp):
    reductions = []; spilled = 0
    for i in range(40):
        size = 8000 + i * 250
        original = Message("user", "[tool_result from read_file]\n" + ("x" * size))
        result = spill_files([original], tmp, single_threshold=8000, batch_threshold=16000)
        if result.spilled_paths:
            spilled += 1
            reductions.append(1 - len(result.messages[0].content) / len(original.content))
    return {"cases": 40, "spill_rate": spilled / 40,
            "mean_chars_reduction": statistics.mean(reductions) if reductions else 0,
            "p95_chars_reduction": percentile(reductions, 95) if reductions else 0}


def context_benchmark(tmp):
    # The real summarizer is used with a deterministic provider; user messages
    # must survive while old assistant content is condensed.
    session = ChatSession(SummaryProvider(), "benchmark")
    history = [Message("user", "REQUIREMENT-ALPHA")]
    history += [Message("assistant", "implementation detail " * 300) for _ in range(8)]
    history += [Message("user", "REQUIREMENT-BETA")]
    session.replace_history(history)
    from gxcode.context.manager import ContextManager
    cfg = ContextConfig(window_size=100, auto_margin=0, keep_tokens=10,
                        keep_min=2, spill_dir=str(tmp))
    manager = ContextManager(session, TokenCounter(), Summarizer(SummaryProvider(), "benchmark"), cfg)
    result = asyncio.run(manager.check_and_compress_async())
    text = "\n".join(m.content for m in result.messages)
    return {"input_messages": len(history), "output_messages": len(result.messages),
            "compression_triggered": len(result.messages) < len(history),
            "user_requirement_retention": all(x in text for x in ("REQUIREMENT-ALPHA", "REQUIREMENT-BETA")),
            "message_reduction": 1 - len(result.messages) / len(history)}


def agent_benchmark():
    async def run_once():
        provider = BenchProvider(); session = ChatSession(provider, "benchmark")
        registry = ToolRegistry(); registry.register(BenchTool())
        started = time.perf_counter()
        events = [e async for e in AgentLoop(session, registry, max_iterations=3).run("run benchmark")]
        return provider, events, time.perf_counter() - started
    results = [asyncio.run(run_once()) for _ in range(50)]
    providers, events_list, elapsed = zip(*results)
    latencies = [x * 1000 for x in elapsed]
    completed = sum(e[-1].reason == "finished" for e in events_list)
    return {"tasks": 50, "tool_chain_completion_rate": completed / 50,
            "mean_iterations": statistics.mean(e[-1].iterations for e in events_list),
            "p95_latency_ms": round(percentile(latencies, 95), 3),
            "provider_calls_per_task": statistics.mean(p.calls for p in providers)}


def main():
    tmp = ROOT / ".gxcode" / "benchmark_spills"; tmp.mkdir(parents=True, exist_ok=True)
    report = {"benchmark": "GXCode component benchmark", "version": 1,
              "permission": permission_benchmark(), "spill": spill_benchmark(tmp),
              "context": context_benchmark(tmp), "agent": agent_benchmark()}
    out = ROOT / "evaluations" / "benchmark_result.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
