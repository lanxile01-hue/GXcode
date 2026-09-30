"""GXCode 近似 Token 估算器

不用精确 tokenizer，用锚定 + 增量字符估算：
- 锚定：记录上次 API 返回的准确 token usage
- 增量：新增消息按 字符数 / chars_per_token 估算
- 锚点失效时（消息被修改/压缩），全量按字符估算
"""

from gxcode.types_ import Message, TokenUsage


class TokenCounter:
    """近似 Token 估算器

    用法:
        counter = TokenCounter()
        # API 调用后设置锚点
        counter.set_anchor(history_snapshot, usage)
        # 后续增量估算
        estimated = counter.estimate(current_history)
    """

    def __init__(self, chars_per_token: float = 4.0):
        self._ratio = chars_per_token
        self._anchor_total: int = 0       # API 上报的 token 总数
        self._anchor_msg_count: int = 0   # 锚定时消息条数
        self._anchor_hashes: list[int] = []  # 锚定时每条消息的 content hash

    def set_anchor(self, messages: list[Message], usage: TokenUsage) -> None:
        """记录锚点：本次 API 调用时的消息快照和实际用量"""
        self._anchor_total = usage.prompt_tokens + usage.completion_tokens
        self._anchor_msg_count = len(messages)
        self._anchor_hashes = [hash(m.content) for m in messages]

    def estimate(self, messages: list[Message]) -> int:
        """估算当前消息列表的总 token 数

        策略：
        - 锚点有效（前 N 条消息未变）→ 只估算增量
        - 锚点失效 → 全量按字符估算
        """
        if self._anchor_msg_count > 0 and len(messages) >= self._anchor_msg_count:
            # 检查锚点是否仍然有效
            if _content_match(
                messages[:self._anchor_msg_count],
                self._anchor_hashes,
            ):
                # 增量估算
                new_chars = sum(
                    len(m.content)
                    for m in messages[self._anchor_msg_count:]
                )
                return self._anchor_total + int(new_chars / self._ratio)

        # 锚点失效或未设置，全量估算
        total_chars = sum(len(m.content) for m in messages)
        return max(1, int(total_chars / self._ratio))


def _content_match(messages: list[Message], hashes: list[int]) -> bool:
    """检查消息列表与锚定的 hash 列表是否匹配"""
    if len(messages) != len(hashes):
        return False
    return all(hash(m.content) == h for m, h in zip(messages, hashes))