# GXCode Ch10 Plan — Skill 系统

## 架构

```
src/gxcode/skills/
├── __init__.py
├── loader.py           # Skill 加载器（三级目录 + frontmatter 解析）
├── registry.py          # Skill 注册中心（两阶段注入管理）
├── executor.py          # 执行器（shared / isolated 模式）
├── whitelist.py         # 工具白名单管理
├── builtin/
│   ├── __init__.py
│   ├── commit.md        # Git 提交规范
│   ├── review.md        # 代码审查
│   └── test.md          # 测试生成

内置于 src/gxcode/skills/builtin/
用户级 ~/.gxcode/skills/
项目级 .gxcode/skills/

工具：
├── load_skill 工具       # 系统级，不受白名单限制
```

## 核心接口

```python
# Skill 数据模型
@dataclass
class Skill:
    name: str
    desc: str
    tools: list[str]       # 白名单工具名列表
    mode: str              # "shared" | "isolated"
    history: int           # isolated 模式带回的历史轮数
    model: str             # 可选指定模型
    params: list[str]      # 参数占位符列表
    body: str              # SOP 正文

# 加载器
class SkillLoader:
    def load_all(project_root) -> list[Skill]
        # 三级目录扫描，同名覆盖

# 注册中心
class SkillRegistry:
    def get_summary() -> str            # 两阶段：摘要列表
    def activate(name, args) -> Skill   # 加载完整指令
    def deactivate_all() -> None
    def get_active_context() -> str     # 激活的上下文

# 执行器
class SkillExecutor:
    async def execute(skill, args, session) -> str
        # shared: 在当前 session 执行
        # isolated: 新 session + 摘要回流
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 解析 | 手动 YAML 行解析 | 不依赖 python-frontmatter |
| 白名单验证 | 启动时在 register 阶段 | 早发现早报错 |
| 激活上下文位置 | system prompt 顶部 | 最显眼 |
| isolated 实现 | 创建临时 ChatSession + Provider | 隔离不影响主历史 |
| 参数占位符 | `{{param}}` 模板替换 | 直观，与 Mustache 兼容 |