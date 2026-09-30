# GXCode Ch03 Plan — Agent Loop

## 架构概览

Ch03 新增 `agent/` 包，ChatSession 退居底层，AgentLoop 成为新编排层：

```
TUI (app.py)            ← 消费 AgentEvent 流
  │
AgentLoop (agent/loop.py)   ← ReAct 循环编排
  ├── StreamCollector (agent/collector.py)  ← 双路收集
  ├── System Prompts (agent/prompts.py)     ← Plan/Act prompt
  │
ChatSession (session.py)   ← 简化：仅管理历史 + 单次 LLM 调用
  │
Provider + Tools            ← 不变
```

- **AgentLoop**：核心编排器，持有 ChatSession 和 ToolRegistry，运行循环直到停止条件
- **StreamCollector**：消费 Provider 的 StreamEvent，实时 yield TextDelta 给 UI，同时累积 TurnResult
- **System Prompts**：生成 Plan/Act 两种模式的 system prompt
- **ChatSession**：简化，只负责管理历史和单次 LLM 调用

## 核心数据结构

```python
@dataclass
class TurnResult:
    text: str
    tool_calls: list[ToolCall]

# Agent 事件类型
TextDelta / ToolCallEvent / ToolResultEvent
IterationStart(iteration, max_iterations)
IterationEnd(iteration, reason)
LoopFinished(summary, iterations, reason)
```

## 核心接口

```python
class AgentLoop:
    def __init__(self, session, registry, max_iterations=25): ...
    async def run(user_message) -> AsyncIterator[AgentEvent]: ...

class StreamCollector:
    def __init__(self, provider, history, model, **options): ...
    async def collect() -> AsyncIterator[TextDelta | ToolCall]: ...
    @property
    def result(self) -> TurnResult: ...
```

## 模块设计

### AgentLoop（`agent/loop.py`）

**职责：** ReAct 循环编排器。

**核心逻辑：**
1. 追加用户消息到历史
2. 循环：IterationStart → StreamCollector.collect() → 检查停止条件 → 执行工具分批 → 回灌历史 → IterationEnd
3. 五种停止条件：FINISHED / MAX_ITERATIONS / CANCELLED / TOOL_ERROR_LOOP / STREAM_ERROR

**依赖：** StreamCollector、ToolRegistry、ChatSession。

### StreamCollector（`agent/collector.py`）

**职责：** 单次 LLM 调用的双路收集器。

- 实时路：TextDelta → yield 给 UI
- 累积路：TextDelta 追加到 buffer，ToolCall 追加到列表
- 流结束后 result 属性产出 TurnResult

**依赖：** Provider。

### System Prompts（`agent/prompts.py`）

- `build_plan_prompt(tools)`：只读模式 prompt
- `build_act_prompt(tools)`：全工具模式 prompt

**依赖：** Tool。

### 工具安全标记（`tools/base.py` 改动）

- `Tool.is_safe: bool = True`
- read_file/glob_find/grep_search → True
- write_file/edit_file/run_command → False

### ChatSession 简化（`session.py` 改动）

去掉工具执行逻辑，回归纯对话历史管理：
- `add_user_message(text)` / `add_assistant_message(text)` / `add_tool_result(content)`
- `stream_chat()` → 纯 LLM 流式调用

### TUI 改动

- Agent 事件处理：IterationStart → 迭代标记，LoopFinished → 完成状态
- `/plan` / `/do` 命令支持

## 文件组织

```
src/gxcode/
├── agent/                   ← 新增
│   ├── __init__.py
│   ├── loop.py
│   ├── collector.py
│   └── prompts.py
├── types_.py                ← 改动（Agent 事件）
├── tools/base.py            ← 改动（is_safe）
├── session.py               ← 改动（简化）
├── tui/app.py               ← 改动（Agent 事件 + plan/do）
└── tui/chat_area.py         ← 改动（迭代标记）
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Agent 编排 | 独立 AgentLoop 类 | 关注点分离 |
| 流式收集 | StreamCollector 组件 | 双路需求 |
| 工具安全标记 | is_safe 类属性 | 简单直观 |
| 取消机制 | asyncio.Event + Task.cancel | 标准库 |
| Plan Mode | 切换 registry + prompt | 轻量 |