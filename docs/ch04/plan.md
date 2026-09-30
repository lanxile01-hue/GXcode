# GXCode Ch04 Plan — 结构化 System Prompt

## 架构概览

Ch04 改造 agent/prompts.py，新增两个文件：

```
PromptBuilder (agent/prompt_builder.py)  ← 模块化组装
PromptInjector (agent/injector.py)       ← 轮次注入逻辑  
agent/prompts.py                         ← 删减：调用 PromptBuilder
agent/loop.py                            ← 改动：注入 Plan/remind
tui/app.py                               ← 改动：/remind 命令
```

## 核心数据结构

```python
# 模块：名称 + 内容函数
Module = tuple[str, int, callable]  # (name, priority, content_fn)

class PromptBuilder:
    def add_module(name, content_fn, priority): ...
    def build(mode, tools, **env) -> str: ...

class PromptInjector:
    def get_plan_reminder(iteration) -> str | None: ...
    @staticmethod
    def wrap_reminder(text) -> str: ...
```

## 模块列表

| 优先级 | 名称 | 内容 |
|--------|------|------|
| 1 | identity | 角色定义 |
| 2 | constraints | 安全边界 |
| 3 | task_mode | Plan/Act |
| 4 | action_rules | 编辑前读等 |
| 5 | tool_usage | 工具列表(动态) |
| 6 | tone_style | 语气风格 |
| 7 | output_format | 输出格式 |

后接 environment（OS/CWD/Shell）

## 模块设计

### PromptBuilder

- `add_module(name, fn, priority)` — 注册模块
- `build(mode, tools, **env)` — 按优先级拼接

### PromptInjector

- `get_plan_reminder(iteration)` — iteration==1 完整，%3==1 简短，其余 None
- `wrap_reminder(text)` — 返回 `[SYSTEM_REMINDER] {text}`

### 其他改动

- prompts.py → 内部改用 PromptBuilder
- loop.py → 每轮注入 Plan 提醒
- tui/app.py → /remind 命令
- tools/file_tools.py → edit_file description 强化

## 文件组织

```
src/gxcode/agent/
├── prompt_builder.py   ← 新增
├── injector.py         ← 新增
├── prompts.py          ← 删减
├── loop.py             ← 改动
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 模块注册 | 函数列表 + 优先级 | 简单 |
| 环境信息 | 独立消息 | 缓存友好 |
| Plan 注入 | 轮次计数 | 无外部依赖 |
| /remind | [SYSTEM_REMINDER] 前缀 | 模型可区分 |