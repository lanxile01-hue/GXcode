"""GXCode Memory 包 — 项目记忆与会话管理

- instructions: 三层项目指令 + @include
- session_store: JSONL 会话存储
- session_recovery: 会话恢复
- notes: 自动笔记 CRUD + 索引
- note_writer: LLM 异步笔记更新
- context_builder: 记忆上下文组装
"""

from gxcode.memory.instructions import load_instructions
from gxcode.memory.session_store import SessionStore, SessionMeta
from gxcode.memory.session_recovery import recover_session, RecoveryResult
from gxcode.memory.notes import Note, NoteManager
from gxcode.memory.note_writer import NoteWriter
from gxcode.memory.context_builder import build_memory_context

__all__ = [
    "load_instructions",
    "SessionStore",
    "SessionMeta",
    "recover_session",
    "RecoveryResult",
    "Note",
    "NoteManager",
    "NoteWriter",
    "build_memory_context",
]