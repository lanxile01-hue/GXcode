"""GXCode ChatSession

管理对话历史，提供 LLM 调用的入口。
Ch03: 简化为薄封装，工具逻辑移到 AgentLoop。
Ch08: 接入 SessionStore，消息自动落盘 JSONL。
Ch09: 工具调用迁移到原生格式 —— assistant 消息携带 tool_calls 字段，
      工具结果以 role="tool" + tool_call_id 回灌。
      旧版把调用写成 "[调用工具] ..." 文本、结果写成 "[tool_result from X]" 用户消息，
      模型在历史里看到的全是文本形式的调用，会模仿着把工具调用写成纯文本
      （不再走 API 的 tool_calls 字段），导致循环误判"任务完成"提前结束。
"""

import json

from gxcode.memory.session_store import SessionStore
from gxcode.provider import Provider
from gxcode.types_ import Message


def _native_tool_calls(tool_calls: list) -> list[dict]:
    """把 ToolCall 事件列表转为 OpenAI tool_calls API 格式"""
    native = []
    for tc in tool_calls:
        native.append({
            "id": getattr(tc, "tool_id", "") or "",
            "type": "function",
            "function": {
                "name": getattr(tc, "name", ""),
                "arguments": json.dumps(
                    getattr(tc, "arguments", None) or {}, ensure_ascii=False
                ),
            },
        })
    return native


class ChatSession:
    """对话会话管理器 — 历史 + LLM 调用 + JSONL 存档"""

    def __init__(
        self,
        provider: Provider,
        model: str,
        thinking: bool = False,
        system_prompt: str = "",
    ):
        self.provider = provider
        self.model = model
        self.thinking = thinking
        self._system_prompt = system_prompt
        self._history: list[Message] = []
        self._store: SessionStore | None = None
        self._session_id: str | None = None

    def set_store(self, store: SessionStore) -> None:
        """接入会话存储，创建新会话 ID"""
        self._store = store
        self._session_id = store.create()

    def _maybe_append(self, role: str, content: str, **extra) -> None:
        if self._store and self._session_id:
            try:
                entry = {"role": role, "content": content, **extra}
                self._store.append(self._session_id, entry)
            except Exception:
                pass  # JSONL 写入失败不阻塞对话

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    def add_system_message(self) -> None:
        """追加 system prompt 到历史（如果尚未存在）"""
        if self._system_prompt and not any(
            m.role == "system" for m in self._history
        ):
            self._history.insert(0, Message(role="system", content=self._system_prompt))

    def add_user_message(self, text: str) -> None:
        self._history.append(Message(role="user", content=text))
        self._maybe_append("user", text)

    def add_assistant_message(self, text: str, tool_calls: list | None = None) -> None:
        """写入 assistant 消息

        tool_calls 非空时以原生 tool_calls 字段存储（不再拼文本摘要），
        模型回看历史时看到的是规范的 function calling 结构，
        而不是可被模仿的 "[调用工具] ..." 文本模式。
        """
        body = (text or "").strip()
        native = _native_tool_calls(tool_calls) if tool_calls else None
        if not body and not native:
            return
        msg = Message(role="assistant", content=body, tool_calls=native)
        self._history.append(msg)
        extra = {"tool_calls": native} if native else {}
        self._maybe_append("assistant", body, **extra)

    def add_tool_result(
        self,
        tool_name: str,
        content: str,
        tool_call_id: str | None = None,
    ) -> None:
        """写入工具结果（role="tool"，携带 tool_call_id 供 OpenAI 协议配对）"""
        self._history.append(Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=tool_name,
        ))
        self._maybe_append(
            "tool_result", content, tool=tool_name, tool_call_id=tool_call_id
        )

    def replace_history(self, messages: list[Message]) -> None:
        """整体替换历史（供 ContextManager 压缩后使用）"""
        self._history = list(messages)