"""GXCode Tool 基类

定义统一的工具接口和工具执行结果类型。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str = ""
    error: str | None = None

    @classmethod
    def ok(cls, output: str) -> "ToolResult":
        return cls(success=True, output=output)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(success=False, error=error)


class Tool(ABC):
    """工具抽象基类

    子类需定义：
    - name: 工具标识名
    - description: 用途描述
    - parameters: JSON Schema 参数定义
    - execute(**kwargs): 执行逻辑
    """

    name: str = ""
    description: str = ""
    is_safe: bool = True  # 是否可并发执行（只读=True，有副作用=False）
    parameters: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": [],
    })

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具，返回结构化结果"""
        ...