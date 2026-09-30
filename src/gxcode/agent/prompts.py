"""GXCode System Prompts

生成 Plan Mode 和 Act Mode 的 system prompt。
Ch04: 内部改用 PromptBuilder 模块化组装。
"""

from gxcode.tools.base import Tool
from gxcode.agent.prompt_builder import PromptBuilder

_builder = PromptBuilder()


def build_plan_prompt(tools: list[Tool]) -> str:
    """Plan Mode prompt — 只读分析，输出结构化计划"""
    return _builder.build(mode="plan", tools=tools)


def build_act_prompt(tools: list[Tool]) -> str:
    """Act Mode prompt — 全工具，ReAct 模式"""
    return _builder.build(mode="act", tools=tools)