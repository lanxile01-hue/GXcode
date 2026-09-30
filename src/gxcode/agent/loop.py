"""GXCode AgentLoop

ReAct 模式的核心循环编排器：
迭代 → LLM 调用 → 工具执行 → 结果回灌 → 下一轮 → 直到停止条件。
"""

import asyncio
import re
from typing import AsyncIterator

from gxcode.agent.collector import StreamCollector
from gxcode.context import ContextManager
from gxcode.session import ChatSession
from gxcode.tools import ToolRegistry
from gxcode.types_ import (
    ContinuationNudge,
    ErrorEvent,
    IterationEnd,
    IterationStart,
    LoopFinished,
    Message,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    ToolResultEvent,
    UsageEvent,
)

# 「我要动手了」类前摇词：短句里出现这些，说明模型在表达意图而非交付结果
_INTENT_HINTS = (
    "让我", "我来", "我再", "再看", "先看", "先读", "先查", "我先", "我直接",
    "我读取", "我查看", "我检查", "我搜索", "我看看", "我将", "我要", "我准备",
    "我去", "继续查看", "继续读", "接下来", "然后我", "接着", "稍等", "现在看",
    "我需要先", "下一步",
)

# 动作对象词：仅当短句同时命中这些词时才判空转（长文本不看）
_ACTION_HINTS = (
    "读取", "查看", "看看", "检查", "搜索", "运行", "执行", "命令",
)

# 已经在交付结论，不能当成空转
_FINISH_MARKERS = (
    "完成", "已修改", "已创建", "已写入", "已删除", "已保存", "已修复",
    "修复了", "总结", "结论", "以上就是", "概览如下", "搞定", "如下",
)

# 空转时注入给模型的纠偏指令
_NUDGE_MESSAGE = (
    "你上一条回复只表达了意图，没有实际调用任何工具，任务并未结束。"
    "如果还需要继续查看或修改，请立即在本轮调用相应工具，不要输出任何解释性文字；"
    "如果任务已经完成，请直接给出完整、可交付的最终答案。"
    "不要只输出「我接下来会去读取…」这类不做事的旁白。"
)

# 伪工具调用检测：模型把工具调用写成文本（模仿旧的 [调用工具] 摘要格式，
# 或 name(key=value) 形式）而没有走 API 的 tool_calls 字段。
# 历史回归：deepseek-chat 曾在第 5 轮输出 286 字的伪调用文本，
# 绕过 120 字的空转检测，被误判为「任务完成」而提前结束循环。
_FAKE_CALL_MARKER = "[调用工具]"
_FAKE_CALL_RE = re.compile(r"([a-z_][a-z0-9_]*)\(\s*[a-z_][a-z0-9_]*\s*=", re.IGNORECASE)

# 伪工具调用纠偏指令
_FAKE_CALL_NUDGE = (
    "你上一条回复把工具调用写成了文本（如 [调用工具] 或 name(key=value) 的形式），"
    "但并没有真正发起任何工具调用，工具没有执行，任务并未结束。"
    "请通过 function calling 机制（tool_calls 字段）重新发起这些调用，"
    "不要在回复文本中书写任何工具调用。"
    "如果任务确实已经完成，请直接给出完整、可交付的最终答案。"
)


class AgentLoop:
    """ReAct Agent 循环编排器

    用法:
        loop = AgentLoop(session, registry, max_iterations=25)
        async for event in loop.run("创建一个 hello.py"):
            # 处理 AgentEvent
    """

    def __init__(
        self,
        session: ChatSession,
        registry: ToolRegistry,
        max_iterations: int = 25,
        permission_checker=None,
        context_manager: ContextManager | None = None,
        confirm_callback=None,
        max_continuation_nudges: int = 2,
    ):
        self._session = session
        self._registry = registry
        self._max_iterations = max_iterations
        # 空转纠偏上限：模型连续输出"前摇旁白"而不调用工具时，最多提醒几次
        self._max_nudges = max_continuation_nudges
        self._cancelled = asyncio.Event()
        self._permission = permission_checker
        self._ctx_mgr = context_manager
        # 人在回路确认回调：async (tool_name, params, reason) -> bool
        # 返回 True 表示放行执行，False 表示拒绝。为 None 时默认拒绝需要确认的工具。
        self._confirm_callback = confirm_callback

    def cancel(self) -> None:
        """外部取消循环"""
        self._cancelled.set()

    async def run(self, user_message: str, reminders: list[str] | None = None):
        """启动 Agent 循环

        Args:
            user_message: 用户输入
            reminders: 可选，每轮迭代前注入的提醒消息列表

        Yields:
            TextDelta | ThinkingDelta | ToolCall | ToolResultEvent |
            IterationStart | IterationEnd | LoopFinished | ContinuationNudge | ErrorEvent
        """
        # 追加用户消息和 system prompt
        self._session.add_system_message()
        self._session.add_user_message(user_message)

        consecutive_errors = 0
        iteration = 0
        nudges_used = 0
        fake_call_nudges_used = 0

        while True:
            # 注入提醒
            if reminders and iteration < len(reminders) and reminders[iteration]:
                self._session.add_user_message(reminders[iteration])

            # 检查取消
            if self._cancelled.is_set():
                yield LoopFinished(
                    summary="已取消",
                    iterations=iteration,
                    reason="cancelled",
                )
                return

            # 检查迭代上限
            if iteration >= self._max_iterations:
                yield LoopFinished(
                    summary="达到迭代上限",
                    iterations=iteration,
                    reason="max_iterations",
                )
                return

            iteration += 1
            yield IterationStart(iteration=iteration, max_iterations=self._max_iterations)

            try:
                # ── 上下文压缩检查（每次 LLM 调用前） ──
                if self._ctx_mgr:
                    ctx_result = await self._ctx_mgr.check_and_compress_async()
                    for ev in ctx_result.events:
                        yield ev

                # ── 收集本轮响应 ──
                collector = StreamCollector(
                    self._session.provider,
                    self._session.history,
                    self._session.model,
                    thinking=self._session.thinking,
                )

                async for event in collector.collect():
                    if isinstance(event, (TextDelta, ThinkingDelta, ToolCall, ErrorEvent, UsageEvent)):
                        yield event

                turn = collector.result

                # 锚定 token 用量
                if self._ctx_mgr and turn.usage:
                    self._ctx_mgr.set_anchor(
                        self._session.history, turn.usage
                    )

                # ── 停止条件：没有工具调用 ──
                # 三种情形要继续迭代而不是当作任务完成：
                # 1. 模型把工具调用写成了文本（伪调用）→ 纠偏让它走 function calling
                # 2. 模型只输出"让我看看…"这类前摇旁白 → 纠偏让它动手或交卷
                # 3. 其余无工具调用的回复 → 真正的最终答案，循环结束
                if not turn.tool_calls:
                    if (
                        self._looks_like_fake_tool_calls(turn.text)
                        and fake_call_nudges_used < self._max_nudges
                        and iteration < self._max_iterations
                    ):
                        fake_call_nudges_used += 1
                        self._session.add_assistant_message(turn.text)
                        self._session.add_user_message(_FAKE_CALL_NUDGE)
                        yield ContinuationNudge(
                            iteration=iteration,
                            text=_FAKE_CALL_NUDGE,
                        )
                        continue

                    if self._is_stalled_preamble(turn.text, iteration, nudges_used):
                        nudges_used += 1
                        self._session.add_assistant_message(turn.text)
                        self._session.add_user_message(_NUDGE_MESSAGE)
                        yield ContinuationNudge(
                            iteration=iteration,
                            text=_NUDGE_MESSAGE,
                        )
                        continue

                    if turn.text:
                        self._session.add_assistant_message(turn.text)
                    yield LoopFinished(
                        summary=turn.text,
                        iterations=iteration,
                        reason="finished",
                    )
                    return

                # ── 检查连续工具错误 ──
                unknown_count = 0
                for tc in turn.tool_calls:
                    try:
                        self._registry.get(tc.name)
                    except KeyError:
                        unknown_count += 1

                if unknown_count > 0 and unknown_count == len(turn.tool_calls):
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        yield LoopFinished(
                            summary="连续工具错误",
                            iterations=iteration,
                            reason="tool_error_loop",
                        )
                        return
                else:
                    consecutive_errors = 0

                # ── 分批执行工具 ──
                # 本轮的工具调用以原生 tool_calls 字段写入历史（不拼文本摘要，
                # 避免模型模仿文本形式的调用而不走 function calling）
                self._session.add_assistant_message(turn.text, tool_calls=turn.tool_calls)

                # 分离安全和不安全的工具调用
                safe_calls = []
                unsafe_calls = []
                for tc in turn.tool_calls:
                    try:
                        tool = self._registry.get(tc.name)
                        if getattr(tool, "is_safe", False):
                            safe_calls.append(tc)
                        else:
                            unsafe_calls.append(tc)
                    except KeyError:
                        unsafe_calls.append(tc)  # 未知工具串行处理

                # 并发执行安全工具
                if safe_calls:
                    tasks = [
                        self._execute_tool(tc) for tc in safe_calls
                    ]
                    results = await asyncio.gather(*tasks)
                    for tc, result in zip(safe_calls, results):
                        yield ToolResultEvent(
                            output=result.output if result.success else "",
                            error=result.error if not result.success else None,
                        )
                        self._session.add_tool_result(
                            tool_name=tc.name,
                            content=result.output if result.success else f"错误: {result.error}",
                            tool_call_id=tc.tool_id,
                        )

                # 串行执行不安全工具
                for tc in unsafe_calls:
                    result = await self._execute_tool(tc)
                    yield ToolResultEvent(
                        output=result.output if result.success else "",
                        error=result.error if not result.success else None,
                    )
                    self._session.add_tool_result(
                        tool_name=tc.name,
                        content=result.output if result.success else f"错误: {result.error}",
                        tool_call_id=tc.tool_id,
                    )

                yield IterationEnd(iteration=iteration, reason="tools_executed")

            except Exception as e:
                yield LoopFinished(
                    summary=f"流错误: {e}",
                    iterations=iteration,
                    reason="stream_error",
                )
                return

    def _looks_like_fake_tool_calls(self, text: str) -> bool:
        """判断文本是否是"伪工具调用"：把调用写成了文字而非 function calling

        判据（任一命中即算）：
        - 含 "[调用工具]" 标记（模仿旧版历史摘要格式）
        - 含 name(key=value) 形式的调用语法，且 name 是已注册的工具名

        只有注册过的工具名才判定，避免把普通代码片段误判成伪调用。
        """
        body = (text or "").strip()
        if not body:
            return False
        if _FAKE_CALL_MARKER in body:
            return True
        for match in _FAKE_CALL_RE.finditer(body):
            candidate = match.group(1)
            try:
                self._registry.get(candidate)
                return True
            except KeyError:
                continue
        return False

    def _is_stalled_preamble(self, text: str, iteration: int, nudges_used: int) -> bool:
        """判断本轮是否是"空转"：说了要做却没真调用工具

        仅在文本明显是短句前摇、且纠偏次数与迭代预算都还有余量时才返回 True。
        正常情况下这是 ReAct 循环里最常见的"模型话说了一半"：
        `if not turn.tool_calls: → finished` 会把它误判成任务完成。

        判据（全部满足才算空转）：
        - 长度 ≤ 120 字：真正的交付物通常更长
        - 不含 ``` / ## 结构标记，也不含"完成/已修改/总结"等结论词
        - 命中前摇词，或「长度 ≤ 80 字 且 命中动作对象词」

        误判代价可控：纠偏最多 2 次，模型若已完工会照常给出答案。
        """
        if nudges_used >= self._max_nudges:
            return False
        if iteration >= self._max_iterations:
            return False
        body = (text or "").strip()
        if not body or len(body) > 120:
            return False
        if "```" in body or "##" in body:
            return False
        if any(mark in body for mark in _FINISH_MARKERS):
            return False
        if any(hint in body for hint in _INTENT_HINTS):
            return True
        # 兜底：很短的句子 + 提到文件/命令类动作对象
        return len(body) <= 80 and any(hint in body for hint in _ACTION_HINTS)

    async def _execute_tool(self, tc: ToolCall):
        """执行单个工具调用"""
        from gxcode.tools.base import ToolResult

        # 权限检查
        if self._permission:
            result = self._permission.check(tc.name, **tc.arguments)
            if not result.allowed:
                return ToolResult.fail(f"权限拒绝: {result.reason}")

            # 层 5: 人在回路确认
            if result.requires_confirm:
                approved = await self._request_confirmation(
                    tool_name=tc.name,
                    params=tc.arguments,
                    reason=result.reason,
                )
                if not approved:
                    return ToolResult.fail(
                        f"用户拒绝了工具调用 '{tc.name}'（{result.reason}）"
                    )

        try:
            tool = self._registry.get(tc.name)
            return await tool.execute(**tc.arguments)
        except KeyError:
            return ToolResult.fail(f"工具 '{tc.name}' 未注册")
        except Exception as e:
            return ToolResult.fail(str(e))

    async def _request_confirmation(self, tool_name: str, params: dict, reason: str) -> bool:
        """请求用户确认执行一个需要人在回路的工具

        若未注入确认回调，默认拒绝（安全兜底）。
        """
        if self._confirm_callback is None:
            return False
        try:
            result = self._confirm_callback(tool_name, params, reason)
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception:
            return False