# GXCode Ch02 Tasks — 工具系统

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/gxcode/tools/__init__.py` | 包初始化 + create_default_registry 工厂 |
| 新建 | `src/gxcode/tools/base.py` | Tool ABC、ToolResult |
| 新建 | `src/gxcode/tools/registry.py` | ToolRegistry |
| 新建 | `src/gxcode/tools/file_tools.py` | read_file、write_file、edit_file |
| 新建 | `src/gxcode/tools/system_tools.py` | run_command、glob_find、grep_search |
| 改动 | `src/gxcode/types_.py` | 新增 ToolCall |
| 改动 | `src/gxcode/provider/anthropic.py` | tool_use 流式解析 |
| 改动 | `src/gxcode/provider/openai.py` | tool_calls 流式解析 |
| 改动 | `src/gxcode/session.py` | 工具执行 + 结果回灌 |
| 改动 | `src/gxcode/tui/chat_area.py` | 工具消息展示方法 |
| 改动 | `src/gxcode/tui/app.py` | ToolCall 事件处理 |
| 改动 | `src/gxcode/main.py` | 注册工具、传递 registry |

## T1: tools 包初始化

**文件：** `tools/__init__.py`

**依赖：** 无

**步骤：**
1. 创建 `src/gxcode/tools/` 目录和 `__init__.py`
2. 导出 `Tool`、`ToolResult`、`ToolRegistry`
3. 实现 `create_default_registry()` 工厂函数，注册六个默认工具

**验证：** `python -c "from gxcode.tools import Tool, ToolRegistry, create_default_registry"` 不报错

## T2: Tool 基类和 ToolResult

**文件：** `tools/base.py`

**依赖：** T1

**步骤：**
1. 定义 `ToolResult` dataclass（`success: bool`、`output: str`、`error: str | None`）
2. 定义 `Tool(ABC)`：类属性 `name`、`description`、`parameters`；抽象方法 `async execute(**kwargs) -> ToolResult`

**验证：** 创建 MockTool 子类，实例化不报错

## T3: ToolRegistry

**文件：** `tools/registry.py`

**依赖：** T2

**步骤：**
1. 实现 `ToolRegistry`：内部 `_tools: dict[str, Tool]`
2. `register(tool)` — 按 name 存储
3. `get(name) -> Tool` — 查找，不存在抛 KeyError
4. `list_all() -> list[Tool]`
5. `to_api_schema() -> list[dict]` — 转为 `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}` 格式

**验证：** 注册 2 个 MockTool，`to_api_schema()` 返回 2 条定义

## T4: 文件工具

**文件：** `tools/file_tools.py`

**依赖：** T2

**步骤：**
1. `ReadFileTool`：`execute(path)` → 读文件，文件不存在返回 ToolResult(success=False)
2. `WriteFileTool`：`execute(path, content)` → 自动创建父目录，写入
3. `EditFileTool`：`execute(path, old_string, new_string)` → 读全文 → count(old) → 0 次报"未找到"、>1 次报"匹配到 N 处" → replace(old, new, 1) → 写回
4. 路径校验：`Path(path).resolve()` 在 `Path.cwd()` 子树内

**验证：** 写 → 读 → 改 → 读，验证内容正确；编辑匹配失败报错

## T5: 系统工具

**文件：** `tools/system_tools.py`

**依赖：** T2

**步骤：**
1. `RunCommandTool`：`execute(command)` → `asyncio.create_subprocess_shell` → `wait_for(communicate(), 30)` → 返回 stdout/stderr/exit_code
2. `GlobFindTool`：`execute(pattern)` → `Path.cwd().glob(pattern)` → 截断 100 条
3. `GrepSearchTool`：`execute(pattern, path)` → `Path.rglob("*")` 遍历 → `re.search` → 截断 50 条

**验证：** `echo hello` 返回 "hello"；`glob_find("*.py")` 返回 .py 文件

## T6: 扩展数据类型

**文件：** `types_.py`（改动）

**依赖：** T1

**步骤：**
1. 新增 `ToolCall` dataclass（`tool_id`、`name`、`arguments`）
2. 更新 `StreamEvent = TextDelta | ThinkingDelta | ToolCall | ErrorEvent`

**验证：** `from gxcode.types_ import ToolCall` 不报错

## T7: AnthropicProvider 工具调用解析

**文件：** `provider/anthropic.py`（改动）

**依赖：** T2、T6

**步骤：**
1. 构造方法接收 `tools: list[dict] | None`，请求体追加 `"tools"`
2. SSE 解析：`content_block_start` type="tool_use" → 记录 name/id
3. `content_block_delta` type="input_json_delta" → 累积 partial_json
4. content_block 结束时 → `json.loads(partial_json)` → yield `ToolCall`

**验证：** 用真实 API 测试工具调用流式解析

## T8: OpenAIProvider 工具调用解析

**文件：** `provider/openai.py`（改动）

**依赖：** T2、T6

**步骤：**
1. 构造方法接收 `tools: list[dict] | None`，请求体追加 `"tools"`
2. SSE 解析：`choices[0].delta.tool_calls[0]` 的 function.name 和 function.arguments 碎片
3. finish_reason="tool_calls" 或结束时 → `json.loads(arguments)` → yield `ToolCall`

**验证：** 用真实 API 测试工具调用流式解析

## T9: ChatSession 工具执行

**文件：** `session.py`（改动）

**依赖：** T3、T6、T7、T8

**步骤：**
1. 构造方法新增 `registry: ToolRegistry` 参数
2. `send()` 中新增 ToolCall 分支：
   - yield ToolCall
   - `tool = registry.get(name)`
   - `result = await tool.execute(**arguments)`
   - 追加 tool_use 和 tool_result 消息到 history
   - yield 结果文本

**验证：** MockTool + MockProvider 测试，验证 history 包含 tool_use/tool_result

## T10: ChatArea 工具消息展示

**文件：** `tui/chat_area.py`（改动）

**依赖：** T6

**步骤：**
1. `add_tool_call(name, args)` — `[yellow][工具][/] 调用 {name}(...)`
2. `add_tool_result(output)` — `[green][结果][/] {output 摘要}`
3. `add_tool_error(error)` — `[red][错误][/] {error}`

**验证：** 在 Textual App 中手动调用，观察样式

## T11: App 工具事件处理

**文件：** `tui/app.py`（改动）

**依赖：** T10

**步骤：**
1. `_handle_input` 事件循环中新增 `isinstance(event, ToolCall)` 分支 → `chat.add_tool_call()`
2. 工具结果文本追加到当前消息

**验证：** 发送工具请求，观察 TUI 展示

## T12: 主入口注册工具

**文件：** `main.py`（改动）

**依赖：** T3、T9

**步骤：**
1. 导入 `create_default_registry`
2. 创建 registry，传入 ChatSession

**验证：** `gxcode` 启动不报错

## T13: 端到端验证

**依赖：** 全部

**步骤：**
1. 输入"读一下 README"→ 观察工具调用
2. 输入"创建 test.txt 写入 hello"→ 验证文件
3. 输入"把 test.txt 的 hello 改成 world"→ 验证编辑
4. 输入"执行 dir"→ 观察命令输出
5. 输入"找 .py 文件"→ 观察 glob 结果

**验证：** 全部 AC 通过

## 执行顺序

```
T1 → T2 → T3 → T4（并行 T5）
         ↓
         T6 → T7（并行 T8）
              ↓
              T9
              ↓
         T10 → T11
              ↓
         T12 → T13
```