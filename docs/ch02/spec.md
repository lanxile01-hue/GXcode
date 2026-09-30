# GXCode Ch02 Spec — 工具系统

## 背景

第一章完成了纯对话 CLI。现在模型只能回答问题，不能操作文件或执行命令。要让 GXCode 从聊天机器人变成真正能干的 Agent，需要给它装上工具系统。

## 目标

- 定义统一的 Tool 抽象接口，所有工具遵循同一套元信息规范
- 实现六个核心工具：读文件、写文件、改文件、执行命令、glob 找文件、grep 搜代码
- 工具注册中心集中管理，生成 API 格式的工具列表
- Provider 层支持解析流式工具调用，执行完成后将结果注入对话历史
- 工具执行带超时保护，失败信息以结构化格式返回模型
- 改文件走原文唯一匹配替换，匹配失败给明确报错让模型重试
- 单次工具调用后停止，不做自动循环

## 功能需求

- **F1: 统一 Tool 接口** — 所有工具实现同一抽象接口：元信息（类属性 `name`、`description`、`parameters`）和执行方法（`async execute(**kwargs) -> ToolResult`）。

- **F2: 六个核心工具**
  - `read_file`：接收 `path`，返回文件内容。文件不存在返回错误。
  - `write_file`：接收 `path` 和 `content`，创建或覆盖写入。父目录不存在时自动创建。
  - `edit_file`：接收 `path`、`old_string`、`new_string`。查找 old_string 唯一出现并替换。零次匹配报"未找到"，多次匹配报"匹配到 N 处，请缩小范围"。
  - `run_command`：接收 `command`，子进程执行，捕获 stdout/stderr/exit_code。默认超时 30 秒。
  - `glob_find`：接收 `pattern`（glob），返回匹配文件路径列表（截断前 100 条）。
  - `grep_search`：接收 `pattern`（正则）和 `path`（目录），返回匹配行及文件路径（截断前 50 条）。

- **F3: 工具注册中心** — 全局注册表，提供 `register(tool)`、`get(name)`、`list_all()`、`to_api_schema()`（转为 LLM API 的 tool definitions 格式）。

- **F4: 工具执行超时与错误处理** — 每个工具统一包超时保护（默认 30 秒）。异常、超时、参数校验失败统一包装为 `ToolResult(success, output, error)`。无论成功失败都返回给模型。

- **F5: 流式工具调用解析** — Provider 在 SSE 流中识别 tool_use 内容块：Anthropic 解析 content_block_start/delta，OpenAI 解析 tool_calls delta 碎片。产出 `ToolCall` 事件。

- **F6: 工具结果回灌对话历史** — ChatSession 收到 ToolCall 后：追加 tool_use 消息 → 执行工具 → 追加 tool_result 消息 → 返回结果文本给 TUI。本轮结束，不自动继续。

- **F7: TUI 工具调用展示** — 对话区用 `[工具]` 前缀区分工具调用和结果，与普通消息样式不同。

## 非功能需求

- **N1: 工具执行隔离** — 工具在独立子进程/异步任务中执行，崩溃不影响 GXCode 进程。
- **N2: 超时保护** — 默认 30 秒超时，超时后强制终止。
- **N3: 文件操作安全** — 路径拒绝 `..` 越权。命令执行以工作目录为 CWD。
- **N4: 流式工具调用延迟** — SSE 碎片拼接延迟与文本流式一致，不引入额外等待。
- **N5: 兼容性** — 不改动第一章 Provider 接口签名。工具未激活时纯对话行为不变。
- **N6: 依赖最小化** — 不引入新的外部 Python 依赖。文件/glob/re/子进程均用标准库。

## 不做的事

- Agent Loop（多轮工具调用）— 留给下一章
- 工具审批/确认弹窗
- 工具并行调用
- 自定义工具插件
- 工具结果缓存
- MCP 协议
- 会话间工具状态持久化

## 验收标准

- **AC1 (F1):** 新增工具类只需继承 Tool 基类、实现元信息 + execute，注册中心自动识别。
- **AC2 (F2):** read_file 读存在的文件返回内容，读不存在返回 `{success: false, error: "..."}`。
- **AC3 (F2):** write_file 自动创建父目录后写入；读取写入的文件内容一致。
- **AC4 (F2):** edit_file 唯一匹配替换正确。零次报"未找到"，多次报"匹配到 N 处"。
- **AC5 (F2):** run_command 执行 `echo hello` 正确捕获输出。执行 `sleep 60` 超时返回错误。
- **AC6 (F2):** glob_find `*.py` 返回当前目录 .py 文件列表。
- **AC7 (F2):** grep_search 正则搜索返回匹配行及文件路径。
- **AC8 (F3):** registry.to_api_schema() 返回含六个工具定义的列表，格式兼容 OpenAI/Anthropic。
- **AC9 (F4):** 工具异常返回 ToolResult(success=false)，不崩溃。
- **AC10 (F5):** 流式解析出完整 ToolCall（工具名 + JSON 参数），不丢失碎片。
- **AC11 (F6):** 工具执行后历史包含 tool_use 和 tool_result 消息。TUI 显示结果摘要。
- **AC12 (F7):** TUI 中工具调用以 `[工具]` 前缀特殊样式展示。
- **AC13 (N3):** `read_file("../../etc/passwd")` 被拒绝。
- **AC14 (N5):** 工具未激活时纯对话行为与第一章一致。