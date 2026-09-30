"""GXCode Agent 包

Agent Loop 编排层，提供 ReAct 模式的自主循环能力。
Ch04: 新增 PromptBuilder 和 PromptInjector。
"""

from gxcode.agent.loop import AgentLoop
from gxcode.agent.collector import StreamCollector
from gxcode.agent.prompt_builder import PromptBuilder
from gxcode.agent.injector import PromptInjector
from gxcode.agent.prompts import build_plan_prompt, build_act_prompt
from gxcode.types_ import TurnResult

__all__ = [
    "AgentLoop",
    "StreamCollector",
    "PromptBuilder",
    "PromptInjector",
    "build_plan_prompt",
    "build_act_prompt",
    "TurnResult",
]