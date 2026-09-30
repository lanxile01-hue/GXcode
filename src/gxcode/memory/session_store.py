"""GXCode 会话 JSONL 存储

追加写 JSONL 文件，不维护独立 meta 文件。
会话 ID 格式：YYYYMMDD-HHMMSS-xxxx（4 位随机 hex 防同秒撞车）。
"""

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class SessionMeta:
    """会话元信息（从 JSONL 文件推算出）"""
    id: str
    title: str           # 第一条用户消息的前 50 字符
    message_count: int
    created_at: str      # ISO 时间戳
    file_path: str


class SessionStore:
    """JSONL 会话存储

    用法:
        store = SessionStore(Path(".gxcode/sessions"))
        sid = store.create()
        store.append(sid, {"role": "user", "content": "hello"})
        sessions = store.list_sessions()
    """

    def __init__(self, sessions_dir: Path):
        self._dir = sessions_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── 创建 ──

    def create(self) -> str:
        """新建会话，返回 session_id"""
        now = datetime.now()
        date_part = now.strftime("%Y%m%d-%H%M%S")
        rand_part = f"{random.randint(0, 0xFFFF):04x}"
        sid = f"{date_part}-{rand_part}"
        # 空文件占位
        (self._dir / f"{sid}.jsonl").touch()
        return sid

    # ── 追加 ──

    def append(self, session_id: str, entry: dict) -> None:
        """追加一行 JSON 到会话文件"""
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now().isoformat()
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        file_path = self._dir / f"{session_id}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line)

    # ── 列会话 ──

    def list_sessions(self) -> list[SessionMeta]:
        """扫描 sessions 目录，推算出所有会话的元信息

        不维护独立 meta 文件，直接读 JSONL 第一行取标题、数行数取消息数。
        """
        result: list[SessionMeta] = []
        for f in sorted(self._dir.glob("*.jsonl"), reverse=True):
            sid = f.stem
            try:
                first_line = _read_first_line(f)
                line_count = _count_lines(f)
                title = ""
                created_at = ""
                if first_line:
                    entry = json.loads(first_line)
                    title = entry.get("content", "")[:50]
                    created_at = entry.get("timestamp", "")
                result.append(SessionMeta(
                    id=sid,
                    title=title or "(空会话)",
                    message_count=line_count,
                    created_at=created_at,
                    file_path=str(f),
                ))
            except (json.JSONDecodeError, OSError):
                # 坏文件跳过，不影响其他会话
                pass
        return result

    # ── 读取 ──

    def read(self, session_id: str) -> list[dict]:
        """读取完整会话（原始 JSON 行列表）

        坏行跳过，不中断读取。
        """
        file_path = self._dir / f"{session_id}.jsonl"
        if not file_path.is_file():
            return []
        entries: list[dict] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    # 坏行跳过
                    pass
        return entries

    # ── 清理 ──

    def cleanup(self, max_age_days: int = 30) -> int:
        """删除超过 max_age_days 天的会话文件，返回删除数量"""
        cutoff = time.time() - max_age_days * 86400
        deleted = 0
        for f in self._dir.glob("*.jsonl"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        return deleted


def _read_first_line(file_path: Path) -> str | None:
    """读取文件第一行"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readline().strip()
    except OSError:
        return None


def _count_lines(file_path: Path) -> int:
    """统计文件行数（大文件友好）"""
    count = 0
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for _ in f:
                count += 1
    except OSError:
        pass
    return count