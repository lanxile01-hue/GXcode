# GXCode Ch08 Tasks — 项目记忆与会话管理

## T1: 项目指令加载
- instructions.py: 三层路径加载 + @include 递归解析
- visited 集合防环路，嵌套深度限制，路径沙箱

## T2: 会话 JSONL 存储
- session_store.py: 追加写、列表（扫文件推 ID/标题/消息数）、读取
- 会话 ID 生成（YYYYMMDD-HHMMSS-xxxx）

## T3: 会话恢复 + 清理
- session_recovery.py: 坏行跳过、孤儿工具截断、token 超限压缩
- 时间跨度提醒、过期清理（30 天）

## T4: 自动笔记存储
- notes.py: 四分类笔记 CRUD、frontmatter Markdown 格式
- 索引文件生成（<= 200 行 / 25KB）

## T5: LLM 笔记更新
- note_writer.py: Agent Loop 结束后异步调 LLM
- 去重判断、增量更新

## T6: 上下文构建 + 集成
- context_builder.py: 指令 + 记忆索引注入 prompt
- main.py + agent/loop.py: 启动时加载记忆、Loop 结束触发笔记更新
- session.py: 接入会话存储（追加写每轮消息）

## T7: 配置 + 文档
- config.py: 记忆相关配置（max_include_depth 等）
- gxcode.yaml.example: 记忆配置示例
- docs/ch08/: spec/plan/checklist（已完成）