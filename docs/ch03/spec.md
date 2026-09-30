# GXCode Ch03 Spec — Agent Loop

## 背景

第二章工具系统让模型能读文件、写文件、执行命令，但每次工具调用后不走下一步。要让 GXCode 变成自主干活的 Agent，需要给它一个循环：思考 → 行动 → 观察 → 再思考，直到任务完成。同时新增 Plan Mode 两段式规划能力。

## 目标

- 实现 ReAct 模式的 Agent Loop，自动循环调用 LLM 和执行工具
- 五种停止条件：模型不再要工具、达到迭代上限、用户取消、连续调未知工具、流错误
- 统一的异步事件流（文本、工具调用、工具结果、Token 用量、进度），Agent 与 UI 解耦
- 流式收集器双路：实时推送文本到 UI，同时攒完整响应用于后续判断
- 多工具调用按安全性分批：只读工具并发，有副作用的串行
- Plan Mode 两段式：/plan 只放开读类工具先出计划，/do 切回全工具执行

## 功能需求

- **F1: ReAct Agent Loop** — 核心循环：迭代 → 调 LLM → 收集回复（文本 + 工具调用）→ 执行工具 → 结果写入历史 → 下一轮 → 直到停止条件。每轮完整历史传给下一轮。

- **F2: 五种停止条件**
  - FINISHED：模型回复不含工具调用
  - MAX_ITERATIONS：达到上限（默认 25 轮，可配置）
  - CANCELLED：用户 Ctrl+C 取消
  - TOOL_ERROR_LOOP：连续 3 轮调到未注册工具
  - STREAM_ERROR：LLM 流错误

- **F3: 异步事件流** — Agent Loop 通过 `AsyncIterator[AgentEvent]` 与 UI 通信。事件：`TextDelta`、`ToolCallEvent`、`ToolResultEvent`、`IterationStart(n)`、`IterationEnd(n, reason)`、`TokenUsage`、`LoopFinished(summary)`。

- **F4: 流式收集器双路** — `StreamCollector`：实时路 yield TextDelta 给 UI；累积路拼接文本和工具调用，流结束后产出 `TurnResult(text, tool_calls)` 供 Agent 判断。

- **F5: 多工具调用分批执行** — 安全标记 `safe: true` 的工具（读类）并发；`safe: false` 的工具（写/命令）串行。

- **F6: Plan Mode 两段式** — `/plan` 只注册只读工具（read_file、glob_find、grep_search），模型分析出计划；`/do` 切回全工具执行。

- **F7: System Prompt** — 内置 system prompt 告知模型角色、工具列表、ReAct 思考方式。Plan/Act 模式不同 system prompt。

## 非功能需求

- **N1: 循环性能** — 轮间间隙 < 500ms，工具不阻塞事件循环。
- **N2: 并发安全性** — 多工具并发无竞态，同文件操作通过锁保护。
- **N3: 取消响应** — Ctrl+C 后 2 秒内终止，立即退出。
- **N4: 内存控制** — tool_result 截断至 8000 字符。后续加上下文压缩。
- **N5: 兼容性** — 不改动 Provider/工具接口。ChatSession 不变，新增 AgentLoop 为上层编排器。
- **N6: 依赖最小化** — 无新外部依赖。并发用 asyncio.gather，取消用 Task.cancel。

## 不做的事

- 权限系统
- 上下文压缩
- 用户交互式确认
- 工具结果缓存
- 子 Agent 委托
- 工具超时重试
- Web/网络工具
- Token 预算动态管理

## 验收标准

- **AC1 (F1):** 输入"创建 hello.py 写入 print('hello')，运行它"，Agent 自动 write_file → run_command，最后回复运行结果。
- **AC2 (F1):** 输入"读一下 README.md"，Agent 调用 read_file 后基于内容分析。
- **AC3 (F2-FINISHED):** 纯聊天"你好"，一轮回复，不进入工具循环。
- **AC4 (F2-MAX_ITERATIONS):** max_iterations=2，多步任务第 2 轮后强制停止，提示"达到迭代上限"。
- **AC5 (F2-CANCELLED):** Agent 执行中按两次 Ctrl+C，循环退出，显示"已取消"。
- **AC6 (F2-TOOL_ERROR_LOOP):** 移除所有工具，连续 3 次失败后停止。
- **AC7 (F3):** TUI 中能看到 `[迭代 1/25]`、`[工具]`、`[结果]` 事件标签。
- **AC8 (F4):** StreamCollector 同时推送 UI 和累积完整响应。
- **AC9 (F5):** 一次请求两个 read_file，并发执行，结果几乎同时返回。
- **AC10 (F5):** 同时读写任务，读并发、写串行。
- **AC11 (F6):** `/plan` 只用只读工具，输出计划。`/do` 后获得全工具执行。
- **AC12 (F7):** 对话历史第一条为 system prompt（role=system）。
- **AC13 (N5):** 不启用 Agent Loop 时，纯对话与 Ch02 一致。