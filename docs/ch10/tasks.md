# GXCode Ch10 Tasks — Skill 系统

## T1: Skill 加载器
- loader.py: frontmatter 解析 + 三级目录扫描 + 同名覆盖
- Skill 数据类

## T2: Skill 注册中心
- registry.py: 两阶段注入（摘要/完整指令）+ 激活管理

## T3: 工具白名单 + load_skill 工具
- whitelist.py: 白名单验证 + 应用/恢复
- 内置 load_skill 工具注册到 ToolRegistry

## T4: 执行器
- executor.py: shared 模式（复用当前 session）+ isolated 模式（独立会话+摘要回流）

## T5: 三个内置 Skill
- builtin/commit.md: Git 提交规范
- builtin/review.md: 代码审查
- builtin/test.md: 测试生成

## T6: 集成 + 斜杠命令
- main.py: 启动时加载 Skill 摘要注入 prompt
- tui/app.py: 斜杠命令自动注册 + 清空时清除
- commands/builtin: 用 skill 替换 review 命令

## T7: 文档
- docs/ch10/: spec/plan/checklist/tasks