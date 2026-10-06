# GXCode

命令行 AI 编程助手。用 Python 从零实现一个终端里的 Coding Agent：能对话、能读写文件、能跑命令、能接 MCP 工具，带权限管控和上下文压缩。

不依赖任何 Agent 框架，核心机制（工具协议适配、Agent Loop、权限判定、上下文压缩、记忆与会话）全部自己实现。

## 特性

- **多供应商**：统一抽象 OpenAI / Anthropic 两套协议，配置切换即可换模型，支持 thinking 模式
- **工具系统**：6 个内置文件与系统工具，异常统一收敛为 `ToolResult`，不崩溃
- **Agent Loop**：自动的多轮工具调用闭环，含迭代上限、连续失败熔断、并发安全调度
- **权限系统**：黑名单 + 沙箱路径校验 + 项目/会话两级规则 + 四种权限模式
- **双层上下文压缩**：长工具结果溢写磁盘留预览，超窗口时 LLM 摘要，摘要失败熔断
- **记忆与会话**：三层项目指令（支持 `@include`）、JSONL 会话持久化与崩溃恢复、自动笔记
- **MCP 客户端**：stdio / HTTP 两种传输，两层配置合并，`${VAR}` 环境变量展开
- **Skill 系统**：三级目录加载、两阶段注入、工具白名单、shared / isolated 两种执行模式
- **TUI**：基于 Textual 的终端界面，流式输出、工具调用可视化、权限确认弹窗

## 快速开始

```bash
pip install -e .
cp gxcode.yaml.example gxcode.yaml
# 编辑 gxcode.yaml，填入真实 api_key
gxcode --config gxcode.yaml
```

要求 Python ≥ 3.10。

## 配置

配置文件为 YAML，默认读取 `./gxcode.yaml`，可用 `--config` 指定。

```yaml
active: "deepseek"          # 必须匹配下方某个 providers 的 name

providers:
  - name: "claude"
    protocol: "anthropic"   # anthropic | openai
    model: "claude-sonnet-4-20250514"
    base_url: "https://api.anthropic.com/v1/messages"
    api_key: "sk-ant-xxx"
    thinking: true          # 仅 anthropic 协议生效

  - name: "deepseek"
    protocol: "openai"
    model: "deepseek-chat"
    base_url: "https://api.deepseek.com/v1/chat/completions"
    api_key: "sk-xxx"
```

可选节（不填使用默认值）：

```yaml
context:
  window_size: 200000       # 模型上下文窗口（token）
  auto_margin: 13000        # 自动触发压缩的安全余量
  manual_margin: 3000       # 手动触发压缩的安全余量
  single_threshold: 32000   # 单条工具结果溢写阈值（字符）
  batch_threshold: 64000    # 工具结果合计溢写阈值（字符）
  keep_tokens: 10000        # 摘要时尾部保留 token 数
  keep_min: 5               # 摘要时尾部最少保留消息数
  max_summary_failures: 3   # 摘要连续失败熔断次数

memory:
  max_include_depth: 3      # @include 最大嵌套深度
  cleanup_days: 30          # 会话清理天数
  note_update_enabled: true # 是否启用自动笔记
```

配置缺失、字段不全、`protocol` 非法时，启动阶段给出可读错误并退出，不抛 Traceback。

## 内置工具

| 工具 | 说明 |
| --- | --- |
| `read_file` | 读取文件，路径越界拒绝 |
| `write_file` | 写入文件，自动创建父目录 |
| `edit_file` | 精确字符串替换，未找到 / 多处匹配均报错 |
| `run_command` | 执行 shell 命令，带超时 |
| `glob_find` | 按 glob 模式查找文件 |
| `grep_search` | 正则搜索文件内容 |
| `load_skill` | 加载 Skill 完整指令并激活 |
| `install_skill` | 安装新 Skill |

## 斜杠命令

| 命令 | 别名 | 说明 |
| --- | --- | --- |
| `/help` | `/h` `/?` | 显示帮助信息 |
| `/clear` | `/cls` | 清空聊天区域 |
| `/compact` | | 手动触发上下文压缩 |
| `/plan` | | 切换到计划模式（只读分析） |
| `/do` | `/act` | 切换到执行模式（全工具） |
| `/session` | | 显示当前会话信息 |
| `/memory` | | 显示记忆状态 |
| `/permission` | `/perm` | 显示或切换权限模式 |
| `/status` | `/st` | 显示 token 用量和系统状态 |
| `/review` | `/cr` | 将代码审查提示词送入对话 |

输入 Tab 补全：单匹配直接补全，多匹配弹出菜单。非斜杠输入原样送给 Agent。

## 权限系统

四种模式：`strict`（只读放行，写操作需确认）、`default`（按规则判断，未命中走人在回路）、`permissive`（除黑名单外全部放行）、`custom`（完全按自定义规则）。

三层判定：命令黑名单 → 路径沙箱（拒绝跳出项目目录）→ 项目/会话规则（如 `Bash(git *): allow`）。会话规则优先级高于项目规则。确认框选择 deny 后 Agent Loop 继续运行，不中断。

## Skill

Skill 是带 YAML frontmatter 的 Markdown 文件，按三级目录扫描，同名后加载覆盖先加载：

1. 内置：`src/gxcode/skills/builtin/`
2. 用户：`~/.gxcode/skills/`
3. 项目：`.gxcode/skills/`

```markdown
---
name: review
desc: 对代码变更进行审查
tools: [read_file, run_command]   # 工具白名单，启动时校验
mode: shared                       # shared | isolated
params: [target]                   # {{target}} 占位符
---
你是代码审查助手。请对 `{{target}}` 进行全面的 Code Review。
```

启动时只注入 Skill 摘要列表，调用 `load_skill` 后完整指令才进入上下文。内置 `commit` / `review` / `test` 三个 Skill，加载后自动注册为斜杠命令。

## 记忆与会话

三层项目指令按优先级拼接，支持 `@include` 递归引用（带环路检测与路径沙箱）：

1. `{项目根}/INSTRUCTIONS.md`
2. `{项目根}/.gxcode/instructions.md`
3. `~/.gxcode/instructions.md`

会话以 JSONL 追加写入 `.gxcode/sessions/`，崩溃恢复时跳过损坏行、截断孤儿工具调用，超过 24 小时插入时间跨度提醒，30 天以上自动清理。Agent Loop 自然结束后异步更新笔记（去重由 LLM 判断）。

## MCP

配置文件 `.gxcode/mcp_servers.yaml`（项目级覆盖用户级 `~/.gxcode/mcp_servers.yaml`）：

```yaml
servers:
  test:
    type: stdio
    command: python
    args: ["tests/test_mcp_server.py"]
```

支持 `${VAR}` 环境变量展开。单个 Server 连接失败不影响其他 Server。

## 项目结构

```text
src/gxcode/
  agent/       Agent Loop、流式收集、System Prompt 构建
  commands/    斜杠命令注册、解析、分发、补全
  context/     Token 估算、文件溢写、双层压缩
  mcp/         MCP 客户端、传输层、结果适配
  memory/      项目指令、笔记、会话存储与恢复
  permission/  黑名单、沙箱、规则、模式、判定器
  provider/    OpenAI / Anthropic 协议适配
  skills/      加载、注册、白名单、执行器
  tools/       内置工具与注册表
  tui/         Textual 界面
docs/ch01-10/  逐章设计文档（spec / plan / tasks / checklist）
evaluations/   回归测试与组件基准
```

## 开发

```bash
pip install -e .
python evaluations/run_eval.py          # 核心机制回归测试（30 项）
python evaluations/benchmark.py         # 组件基准
python evaluations/verify_checklist.py  # 验收清单离线核查（58 项）
```

回归测试使用固定 `FakeProvider`，不调用真实模型、无需 API Key，结果写入 `evaluations/latest_result.json`。
`verify_checklist.py --write` 会把通过的验收项回填到 `docs/ch*/checklist.md`，汇总见 `docs/CHECKLIST_STATUS.md`。

## 已知限制

- 回归测试覆盖核心机制（权限、压缩、会话、工具链等），尚未接入真实模型的端到端任务评测
- 118 项验收清单中 58 项已通过离线自动化核查，其余需真实模型或人工观察，见 `docs/CHECKLIST_STATUS.md`
- TUI 交互项（流式渲染、确认弹窗、Tab 补全菜单）需肉眼观察确认，未纳入自动化
- `docs/ch06/` 缺 `spec.md`
