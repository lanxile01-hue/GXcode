# GXCode Spec — 纯对话 CLI

## 背景

需要一个轻量、可扩展的命令行 AI 对话助手。用户启动后进入交互式 TUI，输入问题，实时看到 AI 逐字流式返回的回复。支持多轮对话记忆上下文。后端模型可插拔切换（至少支持 Anthropic Claude 和 OpenAI），通过配置文件管理。

## 目标

- 通过 YAML 配置文件管理多个 LLM 供应商，用户可随时切换
- 启动后进入全屏 TUI 对话界面，支持多轮对话
- 流式输出 AI 回复，不等全部生成完
- Provider 层抽象为统一接口，后续加新后端只需实现接口
- 支持 Claude 的 extended thinking
- 架构模块化，后续可扩展为完整 Agent

## 功能需求

- **F1: YAML 配置管理** — 用户在工作目录或指定路径放置 YAML 配置文件，定义 LLM 供应商连接信息。每个供应商包含六个字段：
  - `name` — 标识名，方便在多个配置中区分
  - `protocol` — 协议类型，取值 `anthropic` 或 `openai`
  - `model` — 模型名称（如 `claude-sonnet-4-20250514`、`gpt-4o`）
  - `base_url` — API 请求地址
  - `api_key` — 认证密钥
  - `thinking` — 可选布尔值，是否启用 extended thinking（仅 `anthropic` 协议生效）
  启动时加载配置，运行时可通过命令切换供应商。

- **F2: TUI 对话界面** — 启动后进入全屏终端交互界面。界面分为两个区域：上方对话区（滚动显示历史消息，区分用户消息和 AI 回复）和下方输入区（回车发送）。

- **F3: 多轮对话记忆** — 每次发送消息时，将完整的对话历史（用户消息 + AI 回复）作为上下文发送给 API。会话期间历史保存在内存中，退出后丢弃（不做持久化）。

- **F4: 流式输出** — 调用 API 时使用 SSE（Server-Sent Events）协议。AI 回复的文本增量实时渲染到对话区，不等全部生成完。

- **F5: Anthropic Claude 后端** — 通过 Messages API 调用 Anthropic Claude 模型。请求体中携带 `messages` 数组作为对话历史，开启 `stream: true`。

- **F6: OpenAI 后端** — 通过 Chat Completions API 调用 OpenAI 模型。请求体中携带 `messages` 数组，开启 `stream: true`。与 Anthropic 使用同一套 `messages` 格式，由 Provider 层做协议适配。

- **F7: Extended Thinking（Claude）** — 当配置文件 `thinking: true` 且协议为 `anthropic` 时，请求体中设置 `thinking` 参数。API 返回的 `thinking` 类型 content block 在 UI 中以折叠或特殊样式展示（区别于正文输出）。

- **F8: Provider 抽象层** — 定义统一的 `Provider` 接口，包含一个核心方法：`stream_chat(messages, model, **options) -> AsyncIterator[str]`。每个后端（AnthropicProvider、OpenAIProvider）独立实现该接口。未来添加新后端只需新增一个实现类。

## 非功能需求

- **N1: 启动速度** — 从命令行输入 `gxcode` 到 TUI 界面渲染完成，应在 1 秒以内（不含首次依赖安装）。
- **N2: 流式延迟** — SSE 接收到第一个 token 到 TUI 渲染该 token，延迟应小于 100ms。
- **N3: 滚动性能** — 对话区包含 500+ 条历史消息时，新消息追加和自动滚动不出现明显卡顿。
- **N4: 错误处理** — 网络断开、API 返回错误（4xx/5xx）、配置缺失或格式错误时，应在 TUI 界面以可读方式展示错误信息，而非崩溃退出。
- **N5: 跨平台** — 支持 Windows、macOS、Linux 三个平台的终端环境。终端尺寸变化时，布局自适应。
- **N6: 依赖最小化** — 外部 Python 依赖控制在 5 个以内（不含间接依赖），核心依赖：`textual`、`httpx`、`pyyaml`。

## 不做的事

- Tool use / Function calling — 纯对话，不调用外部工具
- 文件读写操作 — 不读取、不编辑、不创建文件（配置文件除外）
- 对话持久化 — 退出后对话历史丢失，不做保存/恢复
- 多会话管理 — 一次只一个对话，不支持切换会话
- Markdown 富文本渲染 — 对话区纯文本展示，不做语法高亮、代码块着色
- MCP 协议 / 插件系统 — 留给后续版本
- 多供应商并发 — 一次只使用一个供应商
- 用户自定义 system prompt — 使用内置 system prompt，不做配置

## 验收标准

- **AC1 (F1):** 准备含 2 个供应商的 YAML 配置文件，启动后 A 供应商能正常调用，切换为 B 供应商后也能正常调用。
- **AC2 (F1):** 配置文件 `thinking: true`、协议为 `anthropic` 时，请求中携带 thinking 参数；协议为 `openai` 时，该字段被忽略。
- **AC3 (F2):** 启动后终端进入全屏 TUI，显示对话区和输入区。输入文字回车后，消息出现在对话区。
- **AC4 (F3):** 连续发送 3 条不同话题的消息，AI 的回复能引用第 1 条消息的内容。
- **AC5 (F4):** 发送一条较长的提问，观察 AI 回复在对话区逐字出现，而非等待后一次性显示。
- **AC6 (F5):** 使用 Anthropic 供应商配置，发送"你好"，收到流式回复。
- **AC7 (F6):** 使用 OpenAI 供应商配置，发送"你好"，收到流式回复。
- **AC8 (F7):** 在 Anthropic 配置中启用 thinking，发送复杂问题，对话区显示 thinking 过程（折叠或标记样式），然后显示正文回复。
- **AC9 (F8):** 新增一个 MockProvider（返回固定回复），不改动 TUI 代码，切换配置后能正常使用。
- **AC10 (N4):** 故意使用无效 API Key，界面显示可读的错误信息，不崩溃。
- **AC11 (N5):** 在 Windows/macOS/Linux 任一平台的终端中启动，TUI 正常渲染。缩放终端窗口，布局自适应。