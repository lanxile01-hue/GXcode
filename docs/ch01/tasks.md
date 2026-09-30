# GXCode Tasks — 纯对话 CLI

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `pyproject.toml` | 项目元数据、依赖、entry point |
| 新建 | `.gitignore` | Python 项目忽略规则 |
| 新建 | `gxcode.yaml.example` | 示例配置文件 |
| 新建 | `src/gxcode/__init__.py` | 包初始化 |
| 新建 | `src/gxcode/types_.py` | Message、StreamEvent 等数据类型 |
| 新建 | `src/gxcode/config.py` | YAML 配置加载 |
| 新建 | `src/gxcode/provider/__init__.py` | Provider ABC、create_provider 工厂 |
| 新建 | `src/gxcode/provider/anthropic.py` | AnthropicProvider |
| 新建 | `src/gxcode/provider/openai.py` | OpenAIProvider |
| 新建 | `src/gxcode/session.py` | ChatSession |
| 新建 | `src/gxcode/tui/__init__.py` | TUI 包初始化 |
| 新建 | `src/gxcode/tui/app.py` | GXCodeApp（Textual App） |
| 新建 | `src/gxcode/tui/chat_area.py` | ChatArea widget |
| 新建 | `src/gxcode/tui/input_bar.py` | InputBar widget |
| 新建 | `src/gxcode/main.py` | CLI 入口 |

## T1: 项目脚手架

**文件：** `pyproject.toml`、`.gitignore`、目录结构、`gxcode.yaml.example`

**依赖：** 无

**步骤：**
1. 创建 `pyproject.toml`，声明依赖 `textual`、`httpx`、`pyyaml`，定义 `[project.scripts]` entry point `gxcode = "gxcode.main:main"`
2. 创建 `.gitignore`（`__pycache__/`、`*.egg-info/`、`.venv/`）
3. 创建目录结构：`src/gxcode/provider/`、`src/gxcode/tui/`
4. 创建空的 `__init__.py` 文件
5. 创建 `gxcode.yaml.example` 示例配置文件（包含一个 Anthropic 和一个 OpenAI 配置示例）

**验证：** `pip install -e .` 不报错

## T2: 共享数据类型

**文件：** `types_.py`

**依赖：** T1

**步骤：**
1. 定义 `Message` dataclass（`role: str`、`content: str`）
2. 定义 `TextDelta`、`ThinkingDelta`、`ErrorEvent` dataclass
3. 定义 `StreamEvent = TextDelta | ThinkingDelta | ErrorEvent` 联合类型

**验证：** `python -c "from gxcode.types_ import Message, StreamEvent"` 不报错

## T3: 配置加载

**文件：** `config.py`

**依赖：** T1

**步骤：**
1. 定义 `ProviderConfig` dataclass（`name`、`protocol`、`model`、`base_url`、`api_key`、`thinking: bool = False`）
2. 定义 `AppConfig` dataclass（`providers: list[ProviderConfig]`、`active: str`）
3. 实现 `load_config(path: str) -> AppConfig`：读 YAML、验证必填字段、返回 AppConfig
4. 实现 `get_active(config: AppConfig) -> ProviderConfig`

**验证：** 用 `gxcode.yaml.example` 测试 `load_config()`，打印结果确认字段正确

## T4: Provider 抽象基类 & 工厂

**文件：** `provider/__init__.py`

**依赖：** T2、T3

**步骤：**
1. 定义 `Provider(ABC)` 抽象类，声明 `async def stream_chat(messages, model, **options) -> AsyncIterator[StreamEvent]`
2. 实现 `create_provider(config: ProviderConfig) -> Provider` 工厂函数：按 `protocol` 字段分发

**验证：** `python -c "from gxcode.provider import Provider, create_provider"` 不报错；传入无效 protocol 抛异常

## T5: AnthropicProvider

**文件：** `provider/anthropic.py`

**依赖：** T4

**步骤：**
1. 实现 `AnthropicProvider(Provider)`，构造方法接收 `ProviderConfig`
2. 实现 `stream_chat`：
   - 构造请求体（`model`、`messages`、`stream: true`）
   - 若 `thinking: true`，追加 `thinking: {"type": "enabled", "budget_tokens": 4000}`
   - 请求头 `x-api-key`、`anthropic-version: 2023-06-01`
   - `httpx.stream("POST", ...)` 发请求
   - 逐行读 SSE：`data: {...}` 行解析 JSON
   - `content_block_delta` 中，`type == "text_delta"` → `TextDelta`
   - `type == "thinking_delta"` → `ThinkingDelta`
   - HTTP 错误 → `ErrorEvent`

**验证：** 用真实 API Key 手动测试流式返回

## T6: OpenAIProvider

**文件：** `provider/openai.py`

**依赖：** T4

**步骤：**
1. 实现 `OpenAIProvider(Provider)`，构造方法接收 `ProviderConfig`
2. 实现 `stream_chat`：
   - 构造请求体（`model`、`messages`、`stream: true`）
   - 请求头 `Authorization: Bearer {api_key}`
   - `httpx.stream("POST", ...)` 发请求
   - 逐行读 SSE：`data: {...}` 行解析 JSON
   - `choices[0].delta.content` → `TextDelta`
   - HTTP 错误 → `ErrorEvent`

**验证：** 用真实 API Key 手动测试流式返回

## T7: ChatSession

**文件：** `session.py`

**依赖：** T2、T4

**步骤：**
1. 实现 `ChatSession` 类，持有 `provider: Provider`、`model: str`、`history: list[Message]`、`thinking: bool`
2. 实现 `async send(user_text: str) -> AsyncIterator[StreamEvent]`：
   - `history.append(Message("user", user_text))`
   - `async for event in provider.stream_chat(history, model, thinking=thinking)`：yield event
   - 流结束后，将完整的 AI 回复文本追加到 history

**验证：** 用 MockProvider（返回固定 StreamEvent 序列），验证 session 正确产生事件并追加 assistant 消息到 history

## T8: ChatArea Widget

**文件：** `tui/chat_area.py`

**依赖：** T2

**步骤：**
1. 继承 `textual.widgets.Static`，实现滚动消息列表
2. `add_user_message(text)` — 新增用户消息行（前缀 `▸`）
3. `add_assistant_message()` — 新增 AI 消息块，返回 message_id
4. `append_text(message_id, delta)` — 增量追加文字（模拟流式打字）
5. `append_thinking(message_id, delta)` — 追加 thinking 内容（灰色前缀 `[思考]`）
6. 新消息自动滚动到底部

**验证：** 在 Textual 测试 App 中手动添加消息，观察渲染效果

## T9: InputBar Widget

**文件：** `tui/input_bar.py`

**依赖：** 无

**步骤：**
1. 继承 `textual.widgets.Input`，自定义样式（底部固定）
2. `on_submit` 回调：清除输入框并返回输入文本
3. `disable()` / `enable()` 方法：发送期间禁用防重复

**验证：** 在 Textual 测试 App 中输入文字回车，确认回调触发

## T10: App 组装

**文件：** `tui/app.py`

**依赖：** T7、T8、T9

**步骤：**
1. 继承 `textual.app.App`，CSS 布局：ChatArea 占满上部、InputBar 固定在底部
2. 构造方法接收 `ChatSession`
3. 挂载 InputBar 的 `on_submit` → `self._handle_input(text)`
4. `_handle_input`：
   - 调用 `chat_area.add_user_message(text)`
   - 禁用 input
   - `message_id = chat_area.add_assistant_message()`
   - `async for event in session.send(text)`：匹配 TextDelta/ThinkingDelta/ErrorEvent 并调用 chat_area 方法
   - 启用 input

**验证：** 导入不报错，CSS 布局语法正确

## T11: 主入口

**文件：** `main.py`

**依赖：** T3、T10

**步骤：**
1. 实现 `main()` 函数：
   - 解析 CLI 参数（`--config` 路径，默认 `./gxcode.yaml`）
   - `load_config(config_path)`
   - `create_provider(get_active(config))`
   - 创建 `ChatSession(provider=..., model=..., thinking=...)`
   - `app = GXCodeApp(session)` → `app.run()`

**验证：** `pip install -e .` 后 `gxcode --help` 显示用法

## T12: 端到端验证

**依赖：** 全部

**步骤：**
1. 复制 `gxcode.yaml.example` 为 `gxcode.yaml`，填入真实 API Key
2. `gxcode` 启动 → TUI 渲染 → 输入"你好" → 观察流式回复
3. 切换供应商 → 重启 → 验证另一后端可用
4. Anthropic thinking 模式 → 验证 thinking 折叠展示

**验证：** 全部 AC 通过

## 执行顺序

```
T1 → T2 → T3
      ↓     ↘
      T4 ──→ T5（并行 T6）
      ↓
      T7 + T8（并行 T9）
      ↓
      T10
      ↓
      T11
      ↓
      T12
```