"""GXCode StreamCollector

单次 LLM 调用的双路收集器：
- 实时路：TextDelta 直接 yield 给 UI
- 累积路：拼接完整文本 + 收集工具调用
"""

from typing import AsyncIterator

from gxcode.provider import Provider
from gxcode.types_ import (
    ErrorEvent,
    Message,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    TokenUsage,
    ToolCall,
    TurnResult,
    UsageEvent,
)


class StreamCollector:
    """流式收集器 — 双路：实时推送 + 累积结果"""

    def __init__(
        self,
        provider: Provider,
        history: list[Message],
        model: str,
        **options,
    ):
        self._provider = provider
        self._history = history
        self._model = model
        self._options = options
        self._text_buffer: str = ""
        self._tool_calls: list[ToolCall] = []
        self._usage: TokenUsage | None = None

    async def collect(self) -> AsyncIterator[TextDelta | ThinkingDelta | ToolCall | ErrorEvent]:
        """实时遍历 LLM 流，yield 事件给 UI，同时内部累积"""
        async for event in self._provider.stream_chat(
            self._history,
            self._model,
            **self._options,
        ):
            if isinstance(event, TextDelta):
                self._text_buffer += event.content
                yield event

            elif isinstance(event, ThinkingDelta):
                self._text_buffer += event.content
                yield event

            elif isinstance(event, ToolCall):
                self._tool_calls.append(event)
                yield event

            elif isinstance(event, UsageEvent):
                self._usage = event.usage
                yield event

            elif isinstance(event, ErrorEvent):
                yield event

    @property
    def result(self) -> TurnResult:
        """流结束后的累积结果"""
        return TurnResult(
            text=self._text_buffer.strip(),
            tool_calls=self._tool_calls,
            usage=self._usage,
        )