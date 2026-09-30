# GXCode Ch02 Plan — 工具系统

## 架构概览

Ch02 在 Ch01 基础上新增一个模块，改动四个现有模块：

```
Ch02 新增：
  tools/                  ← 工具系统
    ├── base.py           Tool ABC、ToolResult
    ├── registry.py       注册中心
    ├── file_tools.py     read_file、write_file、edit_file
    └── system_tools.py   run_command、glob_find、grep_search

Ch02 改动：
  types_.py               ← 新增 ToolCall、ToolResult 类型
  provider/anthropic.py   ← 解析 tool_use 事件
  provider/openai.py      ← 解析 tool_calls delta
  session.py              ← 收到 ToolCall 后执行工具并回灌
  tui/app.py              ← 展示工具调用和结果
  tui/chat_area.py        ← 新增工具消息方法
```

## 核心数据结构

```python
# 工具执行结果
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None

# 工具调用事件
@dataclass
class ToolCall:
    tool_id: str
    name: str
    arguments: dict
```

StreamEvent 扩展为：`TextDelta | ThinkingDelta | ToolCall | ErrorEvent`

## 核心接口

```python
class Tool(ABC):
    name: str
    description: str
    parameters: dict       # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

class ToolRegistry:
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool: ...
    def list_all(self) -> list[Tool]: ...
    def to_api_schema(self) -> list[dict]: ...
```

## 模块设计

### Tool 基类（`tools/base.py`）

**职责：** 定义 Tool ABC 和 ToolResult 数据结构。

**对外接口：**
- `Tool.name` — 类属性，工具标识名
- `Tool.description` — 类属性，用途描述
- `Tool.parameters` — 类属性，JSON Schema 参数定义
- `Tool.execute(**kwargs) -> ToolResult` — 抽象方法

**依赖：** 无内部依赖。

### ToolRegistry（`tools/registry.py`）

**职责：** 集中登记工具、按名查找、生成 API schema。

**对外接口：**
- `register(tool)`、`get(name)`、`list_all()`、`to_api_schema()`

**依赖：** `Tool`。

### 文件工具（`tools/file_tools.py`）

**职责：** read_file、write_file、edit_file。

**实现要点：**
- read_file：读文件内容，处理 FileNotFoundError
- write_file：`Path(parent).mkdir(parents=True, exist_ok=True)` → 写入
- edit_file：读全文 → `str.count(old)` → 0 次报"未找到"，>1 次报"匹配到 N 处，请缩小范围" → `str.replace(old, new, 1)` → 写回
- 所有 path 参数校验：`Path(path).resolve()` 必须在 `Path.cwd()` 子树内

**依赖：** `Tool`、`ToolResult`。

### 系统工具（`tools/system_tools.py`）

**职责：** run_command、glob_find、grep_search。

**实现要点：**
- run_command：`asyncio.create_subprocess_shell` → `asyncio.wait_for(proc.communicate(), timeout=30)`
- glob_find：`Path.cwd().glob(pattern)` → 截断 100 条
- grep_search：`Path(path).rglob("*")` 遍历文件 → `re.search` → 截断 50 条

**依赖：** `Tool`、`ToolResult`。

### Provider 层改动

**AnthropicProvider：**
- 请求体追加 `"tools": registry.to_api_schema()`
- 解析 `content_block_start`（tool_use）和 `content_block_delta`（input_json_delta）→ 拼接 JSON → yield `ToolCall`

**OpenAIProvider：**
- 请求体追加 `"tools": registry.to_api_schema()`
- 解析 `choices[0].delta.tool_calls` 中 function.name 和 function.arguments 碎片 → yield `ToolCall`

**ChatSession 改动：**
- 构造方法接收 `registry: ToolRegistry`
- `send()` 中收到 `ToolCall` → 执行工具 → 追加 tool_use/tool_result 消息 → 返回结果

**TUI 改动：**
- ChatArea 新增 `add_tool_call(name, args)`、`add_tool_result(output)`、`add_tool_error(error)`
- App `_handle_input` 新增 ToolCall 和 ToolResult 的处理分支

## 文件组织

```
src/gxcode/
├── tools/                   ← 新增
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── file_tools.py
│   └── system_tools.py
├── types_.py                ← 改动（新增 ToolCall、ToolResult）
├── provider/
│   ├── __init__.py          ← 改动（StreamEvent 新增 ToolCall）
│   ├── anthropic.py         ← 改动（tool_use 解析）
│   └── openai.py            ← 改动（tool_calls 解析）
├── session.py               ← 改动（工具执行 + 回灌）
└── tui/
    ├── app.py               ← 改动（展示 ToolCall/ToolResult）
    └── chat_area.py         ← 改动（新增工具消息方法）
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Tool 参数 Schema | JSON Schema | OpenAI/Anthropic 通用格式 |
| 工具注册 | 单例全局注册表 | 简单，不需要多注册表 |
| 流式工具参数拼接 | 手动拼接 JSON 字符串 | 两种 API 碎片格式不同 |
| edit_file 替换策略 | `str.replace(old, new, 1)` | 配合 count 校验唯一性 |
| 路径安全 | resolve() 校验在 cwd 子树内 | 防止 .. 越权 |
| 工具超时 | asyncio.wait_for | 标准库 |
| ChatSession 工具逻辑 | 内联在 session.send | 单次调用，不需要 Agent Loop |