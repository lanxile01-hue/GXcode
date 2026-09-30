"""GXCode Context 包 — 双层上下文压缩

轻量预防 (file_spill) + 重量兜底 (summarizer) + ContextManager 编排。
"""

from gxcode.config import ContextConfig
from gxcode.context.token_counter import TokenCounter
from gxcode.context.file_spill import spill_files, SpillResult
from gxcode.context.summarizer import Summarizer, CompressResult
from gxcode.context.manager import ContextManager

__all__ = [
    "TokenCounter",
    "spill_files",
    "SpillResult",
    "Summarizer",
    "CompressResult",
    "ContextManager",
    "ContextConfig",
]