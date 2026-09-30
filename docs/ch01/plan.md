# GXCode Plan — 纯对话 CLI

## 架构概览

系统分为四个模块，按依赖关系自底向上：

```
TUI (Textual)          ← 用户交互层
  │
ChatSession            ← 对话管理 & 流式编排
  │
Provider (ABC)         ← 抽象接口 + 工厂
  │
Config (YAML)          ← 配置加载
```

- **Config**：加载 YAML 配置文件，解析为 `ProviderConfig` 数据对象。提供"当前激活的供应商"查询。
- **Provider**：抽象基类定义统一接口。`AnthropicProvider` 和 `OpenAIProvider` 各自实现 SSE 流式请求，统一输出 `StreamEvent`。
- **ChatSession**：持有消息历史列表，对外提供 `send(message)` 方法，内部调用 Provider 的流式接口，将 `StreamEvent` 逐条 yield 给 TUI。
- **TUI**：Textual App，两个子组件（对话滚动区 + 输入框）。接收 `StreamEvent` 并增量渲染。thinking 事件折叠显示。

## 核心数据结构

```python
# 一条聊天消息
@dataclass
class Message:
    role: str      # "user" | "assistant"
    content: str

# 一个供应商配置（对应 YAML 中一个条目）
@dataclass
class ProviderConfig:
    name: str
    protocol: str  # "anthropic" | "openai"
    model: str
    base_url: str
    api_key: str
    thinking: bool = False

# 顶层配置
@dataclass
class AppConfig:
    providers: list[ProviderConfig]
    active: str  # 当前激活的 provider name

# SSE 流式输出的统一事件类型（由 Provider 产出，TUI 消费）
@dataclass
class TextDelta:
    content: str

@dataclass
class ThinkingDelta:
    content: str

@dataclass
class ErrorEvent:
    message: str

StreamEvent = TextDelta | ThinkingDelta | ErrorEvent
```

## 核心接口

```python
class Provider(ABC):
    async def stream_chat(
        self,
        messages: list[Message],
        model: str,
        **options
    ) -> AsyncIterator[StreamEvent]:
        ...
```

## 模块设计

### Config（`config.py`）

**职责：** YAML 配置加载、验证、ProviderConfig 列表管理。

**对外接口：**
- `load_config(path) -> AppConfig`
- `get_active(config: AppConfig) -> ProviderConfig`

**依赖：** 无内部依赖，仅 `pyyaml`。

### Provider（`provider/`）

**职责：** 抽象基类 + 两个具体实现。每个实现负责：构造 HTTP 请求体、发送 SSE 请求、解析 SSE 事件流、产出统一 `StreamEvent`。

**对外接口：**
- `Provider.stream_chat(messages, model, **options) -> AsyncIterator[StreamEvent]`
- `create_provider(config: ProviderConfig) -> Provider` — 工厂函数

**实现要点：**
- `AnthropicProvider`：请求头 `x-api-key`，请求体 `{"model": ..., "messages": [...], "stream": true, "thinking": {...}}`（仅 `thinking=true` 时带 thinking 参数）。解析 SSE 的 `content_block_delta` 事件，区分 `text_delta` 和 `thinking_delta` 类型。
- `OpenAIProvider`：请求头 `Authorization: Bearer`，请求体 `{"model": ..., "messages": [...], "stream": true}`。解析 SSE 的 `choices[0].delta.content`。

**依赖：** `config.ProviderConfig`、`httpx`。

### ChatSession（`session.py`）

**职责：** 持有消息历史 `list[Message]`。接收用户输入，组装完整上下文，调用 Provider，转发流式事件。

**对外接口：**
- `session.send(user_text: str) -> AsyncIterator[StreamEvent]`

**依赖：** `Provider`、`Message`。

### TUI（`tui/`）

**职责：** Textual 全屏终端应用。两个子 widget：
- **ChatArea**（`chat_area.py`）：垂直滚动对话列表。用户消息右对齐，AI 消息左对齐。thinking 内容可折叠。新消息自动滚底。
- **InputBar**（`input_bar.py`）：底部固定输入框，回车发送，发送期间禁用。

**依赖：** `ChatSession`、`StreamEvent`。

## 模块交互（数据流）

```
用户输入 "你好"
  │
  ▼
InputBar.on_submit("你好")
  │
  ▼
App._handle_input("你好")
  │
  ├─► ChatArea.add_message(("user", "你好"))
  │
  ▼
session.send("你好")
  │
  ├─► history.append(Message("user", "你好"))
  ├─► provider.stream_chat(history, model, thinking=...)
  │       │
  │       ├─► httpx.stream("POST", base_url, json=body)
  │       ├─► 逐行解析 "data: {...}" SSE 帧
  │       ├─► yield TextDelta("好")
  │       └─► 流结束
  │
  ├─► yield TextDelta("好")    → ChatArea 增量渲染
  └─► 流结束：history.append(Message("assistant", "你好！"))
```

## 文件组织

```
gxcode/
├── pyproject.toml
├── gxcode.yaml.example
├── src/
│   └── gxcode/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── types_.py
│       ├── provider/
│       │   ├── __init__.py
│       │   ├── anthropic.py
│       │   └── openai.py
│       ├── session.py
│       └── tui/
│           ├── __init__.py
│           ├── app.py
│           ├── chat_area.py
│           └── input_bar.py
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| TUI 框架 | Textual | Python 生态最成熟的异步 TUI，自带布局/滚动/主题 |
| HTTP 客户端 | httpx | 原生异步 + 原生 SSE 支持（`httpx.stream()`） |
| 流式解析 | 手动 SSE 行解析 | Anthropic 和 OpenAI 的 SSE 事件格式有差异，各自 Provider 内处理更干净 |
| thinking 展示 | ChatArea 内折叠 | 不引入额外 widget，用 collapsible 文本块实现 |
| 入口方式 | console_scripts entry point | `pip install -e .` 后直接 `gxcode` 命令启动 |