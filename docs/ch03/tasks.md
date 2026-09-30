# GXCode Ch03 Tasks — Agent Loop

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gxcode/agent/__init__.py` | 包初始化 + 导出 |
| 新建 | `src/gxcode/agent/prompts.py` | System prompts（plan/act） |
| 新建 | `src/gxcode/agent/collector.py` | StreamCollector 双路收集 |
| 新建 | `src/gxcode/agent/loop.py` | AgentLoop 核心循环 |
| 改动 | `src/gxcode/types_.py` | 新增 Agent 事件类型 |
| 改动 | `src/gxcode/tools/base.py` | 新增 is_safe 属性 |
| 改动 | `src/gxcode/session.py` | 简化，去掉工具逻辑 |
| 改动 | `src/gxcode/tui/chat_area.py` | 迭代标记方法 |
| 改动 | `src/gxcode/tui/app.py` | Agent 事件 + plan/do 命令 |
| 改动 | `src/gxcode/main.py` | AgentLoop 集成 |

## T1: System Prompts

**文件：** `agent/prompts.py`

**依赖：** 无

**步骤：**
1. 实现 `build_plan_prompt(tools) -> str`：只读模式 system prompt，引导模型分析并输出计划
2. 实现 `build_act_prompt(tools) -> str`：全工具模式 system prompt，ReAct 思考指引

**验证：** 打印 prompt 确认含工具列表和角色指令

## T2: StreamCollector

**文件：** `agent/collector.py`

**依赖：** Ch02 Provider

**步骤：**
1. 实现 `StreamCollector`：`_text_buffer` 和 `_tool_calls`
2. `collect()` → TextDelta yield + 追加 buffer，ToolCall yield + 追加列表
3. `result` 属性返回 `TurnResult`

**验证：** MockProvider 测试双路收集

## T3: AgentLoop

**文件：** `agent/loop.py`

**依赖：** T2、ToolRegistry、ChatSession

**步骤：**
1. 实现循环：IterationStart → StreamCollector → 停止判断 → 工具分批执行 → 回灌 → IterationEnd
2. 五种停止条件：FINISHED / MAX_ITERATIONS / CANCELLED / TOOL_ERROR_LOOP / STREAM_ERROR
3. 工具分批：safe=True 并发，safe=False 串行
4. 取消支持：asyncio.Event + Task.cancel

**验证：** MockProvider 模拟多轮，验证停止条件

## T4: Agent 包初始化

**文件：** `agent/__init__.py`

**依赖：** T3

**步骤：** 导出 AgentLoop、StreamCollector、TurnResult

**验证：** `from gxcode.agent import AgentLoop` 不报错

## T5: 扩展类型

**文件：** `types_.py`（改动）

**依赖：** 无

**步骤：** 新增 `TurnResult`、`IterationStart`、`IterationEnd`、`LoopFinished` dataclass

**验证：** 导入不报错

## T6: 工具安全标记

**文件：** `tools/base.py`（改动）

**依赖：** 无

**步骤：** 新增 `is_safe: bool = True`，read_file/glob_find/grep_search → True，其余 → False

**验证：** 检查六个工具 is_safe 值

## T7: ChatSession 简化

**文件：** `session.py`（改动）

**依赖：** T3

**步骤：** 去掉工具执行逻辑，只保留历史管理和 LLM 调用方法

**验证：** 纯对话与 Ch01 一致

## T8: ChatArea 迭代标记

**文件：** `tui/chat_area.py`（改动）

**步骤：** 新增 `add_iteration_marker(n, max_n)` 方法

**验证：** 在测试 App 中渲染验证

## T9: App Agent 事件处理

**文件：** `tui/app.py`（改动）

**步骤：**
1. 处理 IterationStart → 显示 `[迭代 N/25]`
2. 处理 LoopFinished → 显示完成状态
3. 支持 `/plan` `/do` 命令切换模式

**验证：** 启动后输入 `/plan` 观察模式切换

## T10: 主入口集成

**文件：** `main.py`（改动）

**步骤：** 创建 AgentLoop 替代 ChatSession.webp 入口

**验证：** `gxcode` 启动，Agent Loop 就绪

## T11: 端到端验证

**步骤：**
1. "创建 hello.py 写入 print('hello')，运行它" → write_file → run_command
2. "读一下 README 和 pyproject.toml" → 双工具并发
3. "/plan 我要做 web 项目" → 只读模式 → "/do" → 全工具
4. Ctrl+C 取消 → 循环立即退出

**验证：** 全部 AC 通过

## 执行顺序

```
T1 → T2 → T3 → T4
              ↓
T5（并行 T6）→ T7 → T8 → T9 → T10 → T11
```