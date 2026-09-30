# GXCode Ch10 Spec — Skill 系统

## 背景

用户经常需要重复输入相同提示词（代码审查、提交规范、测试生成等）。将这些可复用操作封装为 Skill，按需加载，配合工具白名单提升准确率。

## 目标

- YAML frontmatter + Markdown 定义 Skill，三级存放按优先级覆盖
- 两阶段加载：启动时只注入名字+说明，按需加载完整指令+专属工具
- 两种执行模式：共享对话 / 独立会话
- 工具白名单收窄，启动时验证，技能加载工具不受限
- 自动注册斜杠命令、热更新、清空时清 Skill
- 内置 commit / review / test 三个样板

## 功能需求

- **F1: Skill 定义** — YAML frontmatter（name/desc/tools/mode/history/model/params）+ Markdown SOP 正文。参数占位符 `{{param}}` 支持运行时替换。
- **F2: 三级加载** — 项目 `.gxcode/skills/` > 用户 `~/.gxcode/skills/` > 内置 `skills/`。同名按优先级覆盖，单文件解析失败跳过。
- **F3: 两阶段注入** — 启动时只把 `name: 说明` 列表注入 system prompt。通过内置 `load_skill` 工具加载完整指令，激活后钉在上下文最显眼位置。
- **F4: 两种执行模式** — shared（当前对话，结果留主历史）/ isolated（独立会话，摘要回流，可配带多少历史）。
- **F5: 工具白名单** — 启动时验证白名单工具存在，不存在 panic。`load_skill` 是系统工具不受限。
- **F6: 斜杠命令** — 加载 Skill 后自动注册 `/skill_name` 命令，热更新支持，清空对话时清除已激活 Skill。
- **F7: 三个内置 Skill** — commit（Git 提交规范）、review（代码审查）、test（测试生成）。
- **F8: 目录型 Skill** — 目录内放入口 `.md`、专属工具 schema 和脚本。

## 非功能需求

- **N1:** Skill 解析 < 10ms（单个文件）
- **N2:** 白名单验证在启动时完成
- **N3:** 无新外部依赖

## 不做的事

- Skill 市场分发、版本管理
- Skill 运行时动态生成

## 验收标准

- **AC1:** 三级目录同名 Skill 按优先级覆盖
- **AC2:** 启动时只注入 Skill 摘要列表
- **AC3:** `load_skill` 后完整指令出现在上下文
- **AC4:** 白名单工具不存在的 Skill 启动报错
- **AC5:** shared 模式结果留主历史，isolated 摘要回流
- **AC6:** 加载后自动注册斜杠命令
- **AC7:** 清空对话清除已激活 Skill