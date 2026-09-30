"""GXCode 自动笔记存储

每条笔记一个带 frontmatter 的 Markdown 文件，按四分类组织。
索引文件控制在 200 行 / 25KB 以内。
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# 笔记分类
CATEGORIES = [
    "user_preference",
    "correction_feedback",
    "project_knowledge",
    "reference_material",
]

# frontmatter 解析正则
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# 索引行数上限
_MAX_INDEX_LINES = 200
_MAX_INDEX_BYTES = 25_000


@dataclass
class Note:
    """一条记忆笔记"""
    id: str
    category: str
    title: str
    content: str          # Markdown 正文（不含 frontmatter）
    created: str          # ISO 时间戳
    updated: str          # ISO 时间戳

    def to_markdown(self) -> str:
        """序列化为带 frontmatter 的 Markdown"""
        return (
            "---\n"
            f"id: {self.id}\n"
            f"category: {self.category}\n"
            f"title: {self.title}\n"
            f"created: {self.created}\n"
            f"updated: {self.updated}\n"
            "---\n\n"
            f"{self.content}\n"
        )

    @classmethod
    def from_markdown(cls, text: str) -> "Note | None":
        """从 frontmatter + Markdown 文本反序列化"""
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return None
        fm_text = m.group(1)
        body = text[m.end():]

        # 简易 YAML 行解析（不依赖 PyYAML 做 frontmatter）
        fields: dict[str, str] = {}
        for line in fm_text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()

        if "id" not in fields or "category" not in fields:
            return None

        return cls(
            id=fields["id"],
            category=fields.get("category", "project_knowledge"),
            title=fields.get("title", ""),
            content=body.strip(),
            created=fields.get("created", ""),
            updated=fields.get("updated", ""),
        )


class NoteManager:
    """笔记管理 — CRUD + 索引生成

    用法:
        mgr = NoteManager(Path(".gxcode/memory"))
        mgr.write(note)
        index = mgr.build_index()
    """

    def __init__(self, memory_dir: Path):
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def generate_id(self) -> str:
        """生成唯一笔记 ID"""
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        rand = uuid.uuid4().hex[:6]
        return f"note_{ts}_{rand}"

    # ── 读写 ──

    def read(self, note_id: str) -> Note | None:
        """读取单条笔记"""
        file_path = self._dir / f"{note_id}.md"
        if not file_path.is_file():
            return None
        return Note.from_markdown(file_path.read_text(encoding="utf-8"))

    def write(self, note: Note) -> None:
        """写入（创建或更新）笔记"""
        note.updated = datetime.now().isoformat()
        if not note.created:
            note.created = note.updated
        file_path = self._dir / f"{note.id}.md"
        file_path.write_text(note.to_markdown(), encoding="utf-8")

    def delete(self, note_id: str) -> bool:
        """删除笔记，返回是否成功"""
        file_path = self._dir / f"{note_id}.md"
        if file_path.is_file():
            file_path.unlink()
            return True
        return False

    def list_notes(self) -> list[Note]:
        """列出所有笔记，按更新时间降序"""
        notes: list[Note] = []
        for f in sorted(self._dir.glob("*.md")):
            if f.name == "index.md":
                continue
            note = Note.from_markdown(f.read_text(encoding="utf-8"))
            if note:
                notes.append(note)
        notes.sort(key=lambda n: n.updated, reverse=True)
        return notes

    # ── 索引 ──

    def build_index(self) -> str:
        """生成记忆索引（<= 200 行 / 25KB）

        格式：
        # 记忆索引
        ## 用户偏好
        - 标题 [note_id]
        ## 项目知识
        - 标题 [note_id]
        ...
        """
        notes = self.list_notes()

        # 按分类分组
        groups: dict[str, list[Note]] = {c: [] for c in CATEGORIES}
        for note in notes:
            cat = note.category if note.category in CATEGORIES else "project_knowledge"
            groups[cat].append(note)

        lines: list[str] = ["# 记忆索引", ""]
        for cat in CATEGORIES:
            items = groups[cat]
            if not items:
                continue
            label = {
                "user_preference": "用户偏好",
                "correction_feedback": "纠正反馈",
                "project_knowledge": "项目知识",
                "reference_material": "参考资料",
            }.get(cat, cat)
            lines.append(f"## {label}")
            for note in items:
                line = f"- {note.title} [{note.id}]"
                lines.append(line)
            lines.append("")

        # 控制行数和大小
        while len(lines) > _MAX_INDEX_LINES:
            lines.pop()
        text = "\n".join(lines).strip()
        # 如果太大，从尾部截断（优先保留前面的分类）
        while len(text.encode("utf-8")) > _MAX_INDEX_BYTES and lines:
            lines.pop()
            text = "\n".join(lines).strip()

        return text

    def write_index(self) -> None:
        """写入索引文件到磁盘"""
        index_path = self._dir / "index.md"
        index_path.write_text(self.build_index(), encoding="utf-8")