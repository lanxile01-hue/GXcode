"""GXCode PromptInjector

运行时补充指令的注入管理。
- Plan Mode 提醒按轮次注入
- /remind 指令包装器
"""


class PromptInjector:
    """运行时指令注入器"""

    # Plan Mode 完整指令
    PLAN_FULL = "你正处于 Plan Mode。只能使用只读工具（read_file、glob_find、grep_search），不能修改任何文件。分析任务后输出结构化计划。"

    # 简短提醒
    PLAN_BRIEF = "你仍在 Plan Mode，只能读取不能修改。"

    @staticmethod
    def get_plan_reminder(iteration: int) -> str | None:
        """按轮次返回 Plan Mode 提醒

        首轮：完整指令
        每 3 轮：简短提醒
        其余：不注入
        """
        if iteration == 1:
            return PromptInjector.PLAN_FULL
        if iteration % 3 == 1:
            return PromptInjector.PLAN_BRIEF
        return None

    @staticmethod
    def wrap_reminder(text: str) -> str:
        """包装运行时补充指令

        返回带 [SYSTEM_REMINDER] 标签的文本，
        作为 user 消息注入到对话历史。
        """
        return f"[SYSTEM_REMINDER] {text}"