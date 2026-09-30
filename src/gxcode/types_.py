"""GXCode 共享数据类型"""

from dataclasses import dataclass, field
from typing import Union


@dataclass
class Message:
    """一条聊天消息"""
    role: str       # "system" | "user" | "assistant" | "tool"
    content: str
    # assistant 消息的原生工具调用（OpenAI tool_calls API 格式）：
    # [{"id": "...", "type": "function", "function": {"name": "...", "arguments": "{...}"}}]
    tool_calls: list | None = None
    # tool 消息（工具结果）对应的调用 id，OpenAI 协议配对必需
    tool_call_id: str | None = None
    # tool 消息的工具名（Anthropic 降级序列化 / 展示用）
    name: str | None = None


@dataclass
class TextDelta:
    """流式输出的文本增量"""
    content: str


@dataclass
class ThinkingDelta:
    """Claude extended thinking 增量"""
    content: str


@dataclass
class ErrorEvent:
    """错误事件"""
    message: str


@dataclass
class ToolCall:
    """模型发起的工具调用事件"""
    tool_id: str
    name: str
    arguments: dict


@dataclass
class TokenUsage:
    """API 返回的 token 用量"""
    prompt_tokens: int
    completion_tokens: int


@dataclass
class UsageEvent:
    """流式响应结束时的 token 用量事件"""
    usage: TokenUsage


@dataclass
class ToolResultEvent:
    """工具执行结果事件（独立于文本流）"""
    output: str
    error: str | None = None


@dataclass
class SpillEvent:
    """工具结果溢写到磁盘事件"""
    path: str           # 溢写文件路径
    chars_saved: int    # 从对话中移除的字符数


@dataclass
class CompressEvent:
    """LLM 摘要压缩事件"""
    old_count: int       # 被压缩的消息数
    kept_count: int      # 保留的消息数


# ── Agent Loop 事件 ──

@dataclass
class TurnResult:
    """一轮 LLM 响应的完整结果"""
    text: str
    tool_calls: list
    usage: TokenUsage | None = None


@dataclass
class IterationStart:
    """一轮迭代开始"""
    iteration: int
    max_iterations: int


@dataclass
class IterationEnd:
    """一轮迭代结束"""
    iteration: int
    reason: str


@dataclass
class LoopFinished:
    """整个 Agent 循环结束"""
    summary: str
    iterations: int
    reason: str  # "finished" | "max_iterations" | "cancelled" | "tool_error_loop" | "stream_error"


@dataclass
class ContinuationNudge:
    """空转纠偏事件

    模型只输出"让我看看…"这类前摇旁白、却没有发出任何工具调用时，
    循环不会当作任务结束，而是注入一条继续指令并进入下一轮迭代。
    """
    iteration: int
    text: str       # 注入给模型的提醒内容


# 统一的流式事件类型
StreamEvent = Union[TextDelta, ThinkingDelta, ToolCall, ToolResultEvent, UsageEvent, ErrorEvent, "SpillEvent", "CompressEvent", "ContinuationNudge"]