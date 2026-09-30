# GXCode Ch08 Plan — 项目记忆与会话管理

## 架构

```
src/gxcode/memory/
├── __init__.py           # 公开导出
├── instructions.py       # 项目指令加载 + @include 解析
├── session_store.py      # JSONL 会话读写 + 清理
├── session_recovery.py   # 会话恢复逻辑
├── notes.py              # 笔记 CRUD + 索引
├── note_writer.py        # LLM 异步更新笔记 + 去重
└── context_builder.py    # 构建记忆上下文（注入 prompt）

.gxcode/
├── instructions.md       # 项目级指令
├── memory/               # 项目级笔记
│   ├── index.md
│   └── *.md
└── sessions/             # 会话归档

~/.gxcode/
├── instructions.md       # 用户级指令
└── memory/               # 用户级笔记
    ├── index.md
    └── *.md
```

## 核心接口

```python
# 指令加载
def load_instructions(project_root: Path) -> str
    # 三层加载，@include 递归解析，防环路，路径沙箱

# 会话存储
class SessionStore:
    def append(entry: dict) -> None
    def list_sessions() -> list[SessionMeta]  # 扫 JSONL 推算
    def read(session_id: str) -> list[dict]
    def recover(session_id: str) -> list[dict]  # 含裁剪
    def cleanup(max_age_days: int = 30) -> int

# 笔记
class NoteManager:
    def get_index() -> str          # 索引内容（<= 200 行）
    async def update_from_turn(messages, model_output)  # LLM 异步更新

# 上下文构建
def build_memory_context(project_root) -> str
    # instructions + memory index
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 会话格式 | JSONL 追加写 | 崩溃只丢最后一行，不需要 meta 同步 |
| 会话 ID | YYYYMMDD-HHMMSS-xxxx | 可读，防同秒撞车（4 位随机） |
| @include 深度 | 默认 3 层 | 防无限递归，防滥用 |
| 笔记去重 | LLM 判断 | 语义去重比规则准 |
| 笔记更新时机 | Agent Loop 结束后异步 | 不阻塞交互 |
| 索引大小 | <= 200 行 / 25KB | 约 2-3K tokens，内存轻量 |
| 指令优先级 | 项目 > .gxcode > ~/.gxcode | 项目特定覆盖通用