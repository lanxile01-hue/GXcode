# GXCode Ch09 Plan — 命令系统

## 架构

```
src/gxcode/commands/
├── __init__.py          # 公开导出
├── registry.py          # 命令注册中心（元数据 + 冲突检测）
├── parser.py            # 斜杠解析器
├── controller.py        # UIController 界面抽象接口
├── dispatcher.py        # 分流 + 分发
├── builtin/
│   ├── __init__.py
│   ├── help.py          # /help
│   ├── clear.py         # /clear
│   ├── compact.py       # /compact
│   ├── plan.py          # /plan
│   ├── do_.py           # /do
│   ├── session.py       # /session
│   ├── memory.py        # /memory
│   ├── permission.py    # /permission
│   ├── status.py        # /status
│   └── review.py        # /review
└── completion.py        # Tab 补全
```

## 核心接口

```python
# 命令元数据
@dataclass
class Command:
    name: str
    aliases: list[str]
    desc: str
    usage: str
    type: str  # "local" | "ui" | "prompt"
    handler: Callable
    param_hint: str = ""
    hidden: bool = False

# 注册中心
class CommandRegistry:
    def register(cmd: Command) -> None  # 冲突检测 + 注册
    def find(name: str) -> Command | None
    def list_visible() -> list[Command]

# 解析器
def parse_command(text: str) -> tuple[str | None, str]
    # "/plan something" → ("plan", "something")

# 界面控制
class UIController(ABC):
    def add_message(text: str) -> None
    def send_user_message(text: str) -> None
    def set_mode(mode: str) -> None
    def get_token_usage() -> tuple[int, int]
    def refresh_status() -> None

# 分流器
async def dispatch(input_text, registry, controller, agent_handler)
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 处理函数签名 | `(args: str, ctrl: UIController) -> str \| None` | 统一接口，返回值可选用于 prompt 模式 |
| 冲突检测时机 | register() 时触发，非 lazy | 启动即发现，不等运行时 |
| Tab 补全层级 | InputBar 内实现 | 直接操作输入框，UI 感知 |
| 模式切换命令 | /plan 和 /do 两动词 | 比 /mode plan 更直观 |
| UIController | ABC 抽象类 | 命令不绑定 Textual，可测试 |