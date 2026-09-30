"""GXCode ContextManager — 编排两层压缩

每次 API 请求前调用 check_and_compress()：
1. 轻量预防：工具结果溢写存盘
2. Token 估算 + 阈值判断
3. 重量兜底：LLM 摘要早期对话
"""

from pathlib import Path

from gxcode.config import ContextConfig
from gxcode.context.file_spill import spill_files
from gxcode.context.summarizer import CompressResult, Summarizer
from gxcode.context.token_counter import TokenCounter
from gxcode.session import ChatSession
from gxcode.types_ import CompressEvent, SpillEvent, TokenUsage


class ContextManager:
    """双层压缩编排器"""

    def __init__(
        self,
        session: ChatSession,
        counter: TokenCounter,
        summarizer: Summarizer,
        config: ContextConfig,
    ):
        self._session = session
        self._counter = counter
        self._summarizer = summarizer
        self._config = config
        self._spill_dir = Path(config.spill_dir)
        # 已溢写内容的哈希：同一份内容不再二次溢写，
        # 拦截"溢写 → 重读 → 再溢写"的自我递归
        self._spilled_hashes: set[str] = set()

    def check_and_compress(self, auto: bool = True) -> CompressResult:
        """两层检查 + 压缩（同步，不调 LLM）

        轻量预防始终执行。需要重量兜底时返回 success=False，
        调用方应转而调用 check_and_compress_async。
        """
        margin = self._config.auto_margin if auto else self._config.manual_margin
        history = self._session.history

        # 层 1：轻量预防
        spill_result = spill_files(
            history,
            spill_dir=self._spill_dir,
            single_threshold=self._config.single_threshold,
            batch_threshold=self._config.batch_threshold,
            spilled_hashes=self._spilled_hashes,
        )
        if spill_result.spilled_paths:
            self._session.replace_history(spill_result.messages)
            history = spill_result.messages

        # 层 2：Token 估算 + 判断
        estimated = self._counter.estimate(history)
        threshold = self._config.window_size - margin

        if estimated < threshold:
            return CompressResult(messages=history, success=True)

        return CompressResult(messages=history, success=False)

    async def check_and_compress_async(self, auto: bool = True) -> CompressResult:
        """异步版：执行重量兜底的 LLM 调用"""
        margin = self._config.auto_margin if auto else self._config.manual_margin
        history = self._session.history
        ui_events: list = []

        # 层 1：轻量预防
        spill_result = spill_files(
            history,
            spill_dir=self._spill_dir,
            single_threshold=self._config.single_threshold,
            batch_threshold=self._config.batch_threshold,
            spilled_hashes=self._spilled_hashes,
        )
        if spill_result.spilled_paths:
            for path in spill_result.spilled_paths:
                ui_events.append(SpillEvent(path=path, chars_saved=0))
            self._session.replace_history(spill_result.messages)
            history = spill_result.messages

        # 层 2：Token 估算 + 判断
        estimated = self._counter.estimate(history)
        threshold = self._config.window_size - margin

        if estimated < threshold:
            return CompressResult(messages=history, success=True, events=ui_events)

        # 层 2：重量兜底
        old_count = len(history)
        result = await self._summarizer.compress(
            history,
            self._counter,
            keep_tokens=self._config.keep_tokens,
            keep_min=self._config.keep_min,
        )

        if result.success:
            ui_events.append(CompressEvent(
                old_count=old_count,
                kept_count=len(result.messages),
            ))
            self._session.replace_history(result.messages)
        result.events = ui_events + result.events
        return result

    def set_anchor(self, messages: list, usage: TokenUsage) -> None:
        """用当前历史快照和 API usage 设置 token 估算锚点

        由 AgentLoop 在每轮 LLM 调用完成后调用。
        """
        self._counter.set_anchor(messages, usage)