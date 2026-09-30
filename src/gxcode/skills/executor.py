"""GXCode Skill 执行器

两种执行模式：
- shared: 在当前对话中执行，结果留在主历史
- isolated: 开独立会话，完成后摘要回流
"""

from gxcode.skills.loader import Skill


class SkillExecutor:
    """Skill 执行器"""

    def execute_shared(self, skill: Skill, args: str = "") -> str:
        """共享模式：返回带参数替换的 SOP 指令"""
        body = skill.body
        if args and skill.params:
            arg_values = args.split()
            for i, param in enumerate(skill.params):
                placeholder = f"{{{{{param}}}}}"
                value = arg_values[i] if i < len(arg_values) else ""
                body = body.replace(placeholder, value)
        return body

    async def execute_isolated(
        self, skill: Skill, args: str, history_snapshot: list, provider, model: str
    ) -> str:
        """独立模式：新会话执行，摘要回流（简化实现）"""
        body = self.execute_shared(skill, args)
        # 隔离执行需要独立 ChatSession + AgentLoop
        # 当前简化：直接返回指令让主会话执行
        return body