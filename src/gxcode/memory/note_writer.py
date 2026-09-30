"""GXCode 自动笔记更新 — LLM 异步分析对话生成记忆

Agent Loop 自然结束后异步调 LLM，分析对话提取值得记录的信息。
去重由 LLM 判断：内容重复→合并，新内容→追加，无价值→跳过。
"""

import logging
from pathlib import Path

from gxcode.memory.notes import CATEGORIES, Note, NoteManager
from gxcode.provider import Provider
from gxcode.types_ import Message, TextDelta

logger = logging.getLogger("gxcode.note_writer")
_log_handler = None  # 模块级，防止重复添加 handler

# 笔记更新 Prompt
_NOTE_WRITER_PROMPT = """\
你是一个记忆管理助手。分析以下对话，提取值得长期记住的信息。

## 现有笔记
{existing_notes}

## 对话历史
{conversation}

## 任务
从对话中提取值得记录的信息，按以下四类输出：

- **user_preference** — 用户的编码风格、工具偏好、工作习惯
- **correction_feedback** — 用户对 Agent 的纠正、反馈、表扬或批评
- **project_knowledge** — 项目架构、技术栈、关键文件路径、命名约定
- **reference_material** — 重要的参考链接、文档引用、外部知识

## 规则
1. 如果内容与现有笔记重复，使用 action=update 并指定 note_id
2. 如果是新内容，使用 action=add
3. 如果没有值得记录的信息，只输出 NONE
4. 每条笔记的 title 控制在 30 字以内
5. content 用简洁的 Markdown 写，1-3 段即可

## 输出格式
每条笔记用 --- 分隔，每段格式：

---BEGIN_NOTE---
category: {{category}}
title: {{简短标题}}
action: add | update
note_id: {{如果要更新已有笔记，填写 id，否则留空}}
content: |
  {{Markdown 笔记内容}}
---END_NOTE---

如果没有值得记录的内容，输出：
NONE
"""


class NoteWriter:
    """LLM 驱动的笔记更新器

    用法:
        writer = NoteWriter(provider, model, project_mgr, user_mgr)
        updated = await writer.update(conversation_messages)
    """

    def __init__(
        self,
        provider: Provider,
        model: str,
        project_mgr: NoteManager,
        user_mgr: NoteManager,
    ):
        self._provider = provider
        self._model = model
        self._project = project_mgr
        self._user = user_mgr
        self._setup_file_log()

    def _setup_file_log(self) -> None:
        """将 NoteWriter 日志同时写入文件（仅首次添加 handler）"""
        global _log_handler
        if _log_handler is not None:
            return
        try:
            log_dir = Path(".gxcode") / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            _log_handler = logging.FileHandler(log_dir / "note_writer.log", encoding="utf-8")
            _log_handler.setLevel(logging.DEBUG)
            _log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(_log_handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False  # 不污染根 logger
        except Exception:
            pass  # 文件日志非关键路径

    async def update(self, messages: list[Message]) -> int:
        """分析对话，更新笔记，返回更新的笔记数"""
        # 汇总现有笔记
        existing = self._build_existing_summary()

        # 汇总对话（只取最近 5 轮，约 8000 字符）
        conv_text = _summarize_conversation(messages[-20:])

        if not conv_text.strip():
            return 0

        prompt = _NOTE_WRITER_PROMPT.format(
            existing_notes=existing or "(无现有笔记)",
            conversation=conv_text[:8000],
        )

        # 调 LLM（不带 tools）
        response = await self._call_llm(prompt)
        logger.info("LLM 原始响应 (前500字符): %s", response[:500] if response else "(空)")
        if not response or "NONE" in response.upper():
            logger.info("无笔记更新（LLM 判定无需记录或调用失败）")
            return 0

        # 解析输出
        try:
            updates = _parse_notes(response)
        except Exception as e:
            logger.error("笔记解析失败: %s\n原始响应:\n%s", e, response[:2000])
            return 0
        count = 0
        for update in updates:
            if update.get("action") == "add":
                note = Note(
                    id=self._project.generate_id(),
                    category=update.get("category", "project_knowledge"),
                    title=update.get("title", "未命名"),
                    content=update.get("content", ""),
                    created="",
                    updated="",
                )
                self._project.write(note)
                count += 1
            elif update.get("action") == "update" and update.get("note_id"):
                existing_note = self._project.read(update["note_id"])
                if existing_note:
                    existing_note.content = update.get("content", existing_note.content)
                    existing_note.title = update.get("title", existing_note.title)
                    self._project.write(existing_note)
                    count += 1

        if count > 0:
            self._project.write_index()
            logger.info("已更新 %d 条笔记，已写入索引", count)
        return count

    # ── 内部 ──

    def _build_existing_summary(self) -> str:
        """构建现有笔记摘要（给 LLM 做去重参考）"""
        notes = self._project.list_notes()
        if not notes:
            return ""
        lines: list[str] = []
        for n in notes[:30]:  # 最多给 30 条，避免 prompt 过长
            lines.append(f"[{n.id}] ({n.category}) {n.title}")
        return "\n".join(lines)

    async def _call_llm(self, prompt: str) -> str:
        """调 LLM 获取笔记更新建议"""
        from gxcode.types_ import ErrorEvent

        request = [Message(role="user", content=prompt)]
        parts: list[str] = []
        try:
            async for event in self._provider.stream_chat(request, self._model):
                if isinstance(event, TextDelta):
                    parts.append(event.content)
                elif isinstance(event, ErrorEvent):
                    logger.warning("LLM 错误: %s", event.message)
        except Exception as e:
            logger.error("调用失败: %s", e, exc_info=True)
            return ""
        text = "".join(parts)
        if not text:
            logger.warning("LLM 返回空")
        return text


def _summarize_conversation(messages: list[Message]) -> str:
    """压缩对话为文本（只保留角色和内容摘要）"""
    lines: list[str] = []
    for m in messages:
        role = m.role
        content = m.content[:500]  # 每条消息最多 500 字符
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def _parse_notes(text: str) -> list[dict]:
    """解析 LLM 输出的笔记块"""
    # 按 ---BEGIN_NOTE--- 分割
    blocks = text.split("---BEGIN_NOTE---")
    results: list[dict] = []
    for block in blocks:
        if "---END_NOTE---" not in block:
            continue
        block = block.split("---END_NOTE---")[0].strip()
        if not block:
            continue
        note_data: dict[str, str] = {}
        for line in block.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith(" "):
                key, _, val = line.partition(":")
                note_data[key.strip()] = val.strip()
            elif line.startswith("  ") and "content" in note_data:
                # 续行追加到上一个字段
                pass
        if "category" in note_data and "action" in note_data:
            # 解析 content（可能在 content: | 后面的多行）
            content_start = block.find("content:")
            if content_start >= 0:
                content_text = block[content_start + len("content:"):]
                # 去掉开头的 | 符号
                content_text = content_text.lstrip("| \t")
                note_data["content"] = content_text.strip()
            results.append(note_data)
    return results