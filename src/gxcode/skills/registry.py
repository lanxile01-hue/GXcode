"""GXCode Skill 注册中心

两阶段注入管理：
- 阶段 1（启动）：只注入名字和说明摘要
- 阶段 2（激活）：加载完整指令钉在上下文顶部
"""

from gxcode.skills.loader import Skill


class SkillRegistry:
    """Skill 注册中心 — 两阶段加载 + 激活管理"""

    def __init__(self, skills: dict[str, Skill] | None = None):
        self._skills: dict[str, Skill] = skills or {}
        self._active: dict[str, Skill] = {}  # 已激活的 Skill

    # ── 阶段 1：摘要 ──

    def get_summary(self) -> str:
        """生成 Skill 摘要列表（注入 system prompt）"""
        if not self._skills:
            return ""
        lines = ["## 可用 Skill"]
        for skill in self._skills.values():
            lines.append(f"- {skill.summary}")
        lines.append("使用 load_skill 工具加载完整 Skill")
        return "\n".join(lines)

    # ── 阶段 2：激活 ──

    def activate(self, name: str, args: str = "") -> Skill | None:
        """激活 Skill，加载完整指令

        Args:
            name: Skill 名称
            args: 参数（空格分隔，按 params 顺序替换 {{param}}）
        """
        skill = self._skills.get(name)
        if not skill:
            return None

        # 参数替换
        body = skill.body
        if args and skill.params:
            arg_values = args.split()
            for i, param in enumerate(skill.params):
                placeholder = f"{{{{{param}}}}}"
                value = arg_values[i] if i < len(arg_values) else ""
                body = body.replace(placeholder, value)

        # 创建激活副本（含替换后的 body）
        activated = Skill(
            name=skill.name,
            desc=skill.desc,
            tools=list(skill.tools),
            mode=skill.mode,
            history=skill.history,
            model=skill.model,
            params=list(skill.params),
            body=body,
        )
        self._active[name] = activated
        return activated

    def deactivate(self, name: str) -> None:
        self._active.pop(name, None)

    def deactivate_all(self) -> None:
        self._active.clear()

    def get_active_context(self) -> str:
        """获取激活 Skill 的上下文（钉在 system prompt 顶部）"""
        if not self._active:
            return ""
        parts = ["## 激活的 Skill 指令"]
        for skill in self._active.values():
            parts.append(f"### {skill.name}: {skill.desc}\n{skill.body}")
        return "\n\n".join(parts)

    def get_active_skill(self, name: str) -> Skill | None:
        return self._active.get(name)

    def list_names(self) -> list[str]:
        return list(self._skills.keys())