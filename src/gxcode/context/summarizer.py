"""GXCode 重量兜底 — LLM 结构化摘要

当累积对话逼近窗口上限时，将早期消息压缩为结构化摘要。
- 尾部保留 ~10K token 或至少 5 条近期消息
- 用户消息原文保留，只摘要 assistant/tool_result
- 摘要 Prompt 禁止调工具，先草稿再正式
- 压缩后插入边界消息
- 连续 3 次失败熔断
"""

from dataclasses import dataclass, field

from gxcode.context.token_counter import TokenCounter
from gxcode.provider import Provider
from gxcode.types_ import Message, TextDelta

# 摘要用 system prompt — 禁止调工具，草稿先写再正式
_SUMMARY_SYSTEM = """\
你是一个对话总结助手。将一段 Agent 对话历史总结为结构化摘要。

重要规则：
1. **禁止调用任何工具** — 本次对话未提供工具，只做纯文本总结
2. **先写草稿再写正式摘要** — 先用简短段落理清思路，然后输出正式摘要，草稿用完就丢弃
3. **严格按以下结构输出**

## 任务目标
用户想要完成什么

## 已完成操作
Agent 已经执行了哪些操作（文件读写、命令执行、代码修改等）

## 关键发现
操作过程中的重要发现、错误或注意事项

## 当前状态
任务目前的进展，例如：进行到哪一步、遇到了什么问题

## 待办事项
尚未完成的事项或下一步需要做什么"""

# 边界消息 — 压缩后插入，提醒模型不要脑补
BOUNDARY_MESSAGE = Message(
    role="user",
    content="[系统提示] 以上是对话历史的压缩摘要。"
    "如果你需要之前操作的具体细节（例如文件内容、命令输出），"
    "请使用 read_file 等工具重新读取完整内容，"
    "不要仅凭摘要推断或脑补代码细节。",
)


@dataclass
class CompressResult:
    """压缩结果"""
    messages: list[Message]
    success: bool
    summary: str = ""
    events: list = field(default_factory=list)  # SpillEvent | CompressEvent


class Summarizer:
    """重量兜底：LLM 摘要早期对话

    用法:
        summarizer = Summarizer(provider, model)
        result = await summarizer.compress(history, counter, keep_tokens=10000)
    """

    def __init__(
        self,
        provider: Provider,
        model: str,
        max_failures: int = 3,
    ):
        self._provider = provider
        self._model = model
        self._max_failures = max_failures
        self._consecutive_failures = 0
        self._tripped = False

    @property
    def tripped(self) -> bool:
        """熔断是否已触发"""
        return self._tripped

    async def compress(
        self,
        messages: list[Message],
        counter: TokenCounter,
        keep_tokens: int = 10000,
        keep_min: int = 5,
    ) -> CompressResult:
        """压缩消息列表

        Args:
            messages: 当前完整消息列表
            counter: TokenCounter 实例（用于尾部分割）
            keep_tokens: 尾部保留的 token 数
            keep_min: 尾部至少保留的消息条数

        Returns:
            CompressResult: 压缩后的消息列表
        """
        if self._tripped:
            return CompressResult(messages=messages, success=False)

        # ── 1. 分割 old / recent ──
        split_idx = _split_tail(messages, counter, keep_tokens, keep_min)
        if split_idx <= 0:
            # 消息太少，不需要压缩
            return CompressResult(messages=messages, success=True)

        old_section = messages[:split_idx]
        recent_section = messages[split_idx:]

        # ── 2. 分离 old_section 中的消息 ──
        to_summarize: list[Message] = []  # 要摘要的（非 user）
        user_msgs: list[Message] = []     # 用户原文保留
        for m in old_section:
            if m.role == "user":
                user_msgs.append(m)
            else:
                to_summarize.append(m)

        if not to_summarize:
            # 没有可摘要的内容（old 部分只有 user 消息）
            return CompressResult(messages=messages, success=True)

        # ── 3. 调 LLM 生成摘要 ──
        try:
            summary_text = await self._generate_summary(to_summarize)
        except Exception:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_failures:
                self._tripped = True
            return CompressResult(messages=messages, success=False)

        self._consecutive_failures = 0

        # ── 4. 构造压缩后的消息列表 ──
        compressed: list[Message] = []
        compressed.append(Message(role="user", content=summary_text))
        compressed.extend(user_msgs)
        compressed.extend(recent_section)
        compressed.append(BOUNDARY_MESSAGE)

        return CompressResult(
            messages=compressed,
            success=True,
            summary=summary_text,
        )

    async def _generate_summary(self, to_summarize: list[Message]) -> str:
        """调 LLM 生成结构化摘要（不带 tools）"""
        # 摘要请求全部扁平化为纯文本消息：
        # role="tool" / 带 tool_calls 的 assistant 直接进请求可能破坏
        # OpenAI 协议的配对校验（摘要片段常常是残缺配对），统一降级为文本。
        request_messages = [
            Message(role="system", content=_SUMMARY_SYSTEM),
            *[_flatten(m) for m in to_summarize],
        ]

        text_parts: list[str] = []
        async for event in self._provider.stream_chat(
            request_messages,
            self._model,
        ):
            if isinstance(event, TextDelta):
                text_parts.append(event.content)

        return "".join(text_parts).strip()


def _flatten(m: Message) -> Message:
    """把消息降级为纯文本，保证摘要请求不含 tool 配对结构"""
    if m.role == "tool":
        return Message(role="user", content=f"[tool_result from {m.name or 'tool'}]\n{m.content}")
    if m.role == "assistant" and m.tool_calls:
        calls = "；".join(
            f"{tc.get('function', {}).get('name', '?')}({tc.get('function', {}).get('arguments', '')})"
            for tc in m.tool_calls
        )
        body = f"{m.content}\n[调用工具] {calls}" if m.content else f"[调用工具] {calls}"
        return Message(role="assistant", content=body)
    return m


def _split_tail(
    messages: list[Message],
    counter: TokenCounter,
    keep_tokens: int,
    keep_min: int,
) -> int:
    """从尾部按 token 往回数，找分割点

    Returns:
        分割索引 — messages[:n] 是 old_section, messages[n:] 是 recent_section
    """
    if len(messages) <= keep_min:
        return 0

    tail_tokens = 0
    tail_count = 0
    for i in range(len(messages) - 1, -1, -1):
        # 每条消息按字符估算 token
        tail_tokens += len(messages[i].content) / 4
        tail_count += 1
        if tail_tokens >= keep_tokens and tail_count >= keep_min:
            return _align_split(messages, i)  # messages[i:] = recent, messages[:i] = old

    return 0


def _align_split(messages: list[Message], i: int) -> int:
    """把分割点前移到完整配对边界，避免 assistant.tool_calls 与其 tool 消息被拆开"""
    while i > 0 and (
        messages[i - 1].tool_calls or messages[i - 1].role == "tool"
    ):
        i -= 1
    return i