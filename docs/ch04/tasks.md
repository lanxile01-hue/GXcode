# GXCode Ch04 Tasks — 结构化 System Prompt

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `agent/prompt_builder.py` | PromptBuilder |
| 新建 | `agent/injector.py` | PromptInjector |
| 改动 | `agent/prompts.py` | 改用 PromptBuilder |
| 改动 | `agent/loop.py` | 注入逻辑 |
| 改动 | `agent/__init__.py` | 导出新类 |
| 改动 | `tui/app.py` | /remind 命令 |
| 改动 | `tools/file_tools.py` | edit_file description 强化 |

## T1: PromptBuilder

**文件：** `agent/prompt_builder.py`

**步骤：**
1. 定义 7 个固定模块的内容函数
2. 实现 `PromptBuilder`：`add_module()` + `build()`
3. `build()` 按优先级排序，模块间空行分隔，末尾接环境信息

**验证：** 打印 `build("act", tools)`，确认含 7 个模块

## T2: PromptInjector

**文件：** `agent/injector.py`

**步骤：**
1. `get_plan_reminder(iteration)` — 首轮完整，每 3 轮简短，其余 None
2. `wrap_reminder(text)` — `[SYSTEM_REMINDER] {text}`

**验证：** 测试轮次 1/2/3/4 的返回值

## T3: prompts.py 删减

**文件：** `agent/prompts.py`（改动）

**步骤：** `build_plan_prompt` 和 `build_act_prompt` 内部改用 PromptBuilder

**验证：** 调用方式和返回值与 Ch03 一致

## T4-T6: loop.py / app.py / edit_file 强化

**步骤：**
- loop.py → 注入 Plan 提醒
- app.py → /remind 命令
- file_tools.py → edit_file description 加"必须先 read_file"

**验证：** 端到端测试

## 执行顺序

```
T1 → T2 → T3 → T4（并行 T5、T6）
```