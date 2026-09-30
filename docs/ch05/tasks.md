# GXCode Ch05 Tasks — 权限系统

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `permission/__init__.py` | 导出 |
| 新建 | `permission/blacklist.py` | 高危命令正则 |
| 新建 | `permission/sandbox.py` | 路径沙箱 |
| 新建 | `permission/rules.py` | 规则引擎+YAML |
| 新建 | `permission/modes.py` | 权限模式枚举 |
| 新建 | `permission/checker.py` | 五层编排 |
| 改动 | `agent/loop.py` | 工具执行前检查 |
| 改动 | `tui/app.py` | 确认框+/permission |

## T1: 黑名单 + 沙箱

**文件：** `blacklist.py`、`sandbox.py`

**步骤：**
1. 高危命令正则列表：`rm -rf /`、`mkfs`、`dd if=`、`chmod 777 /`、`> /dev/sd`
2. 沙箱：`resolve()` → 前缀判断
3. 返回 `(allowed, reason)`

## T2: 规则引擎

**文件：** `rules.py`、`modes.py`

**步骤：**
1. `PermissionMode` 枚举：STRICT/DEFAULT/PERMISSIVE/CUSTOM
2. `RuleEngine`：加载三层 YAML，`fnmatch` 匹配
3. 返回 allow/deny/None

## T3: 五层编排

**文件：** `checker.py`

**步骤：** 串联黑名单→沙箱→模式→规则→人在回路

## T4: Agent Loop + TUI

**文件：** `loop.py`、`app.py`

**步骤：**
1. loop.py 在 _execute_tool 前调 checker
2. app.py 人在回路确认框（ModalScreen）

## 执行顺序

```
T1 → T2 → T3 → T4
```