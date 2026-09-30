# GXCode Ch05 Plan — 权限系统

## 架构

```
permission/
├── __init__.py
├── blacklist.py     ← 高危命令正则
├── sandbox.py       ← 路径沙箱
├── rules.py         ← 规则引擎
├── checker.py       ← 五层编排
└── modes.py         ← 权限模式

agent/loop.py ← 工具执行前调用 checker
tui/app.py    ← 人在回路确认框
```

## 核心接口

```python
class PermissionChecker:
    def __init__(mode, project_root, rules_dirs): ...
    def check(tool_name, **params) -> CheckResult: ...

@dataclass
class CheckResult:
    allowed: bool
    reason: str
    requires_confirm: bool

class RuleEngine:
    def load_yaml(path) -> list[Rule]: ...
    def match(tool, params) -> bool | None: ...  # None=未命中

class PermissionMode(Enum):
    STRICT, DEFAULT, PERMISSIVE, CUSTOM
```

## 五层判断

```
工具调用 → 黑名单? → deny
         → 沙箱? → deny
         → 模式=permissive? → allow
         → 模式=strict+写操作? → confirm
         → 规则引擎? → allow/deny
         → 人在回路 → confirm
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 黑名单 | 模块常量 | 不可配置 |
| 规则匹配 | fnmatch | 标准库 glob |
| 规则加载 | 三层 YAML | 优先级清晰 |
| 确认框 | ModalScreen | TUI 内 |