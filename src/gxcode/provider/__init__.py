"""GXCode Provider 层

Provider ABC 定义统一接口，create_provider 工厂按协议分发实例。
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from gxcode.config import ProviderConfig
from gxcode.types_ import Message, StreamEvent


class Provider(ABC):
    """LLM 供应商统一接口"""

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        model: str,
        **options
    ) -> AsyncIterator[StreamEvent]:
        """流式发送对话，逐 token 产出 StreamEvent

        Args:
            messages: 完整对话历史
            model: 模型名称
            **options: 协议特定参数（如 thinking）

        Yields:
            TextDelta | ThinkingDelta | ErrorEvent
        """
        ...


def create_provider(config: ProviderConfig, tools: list[dict] | None = None) -> Provider:
    """工厂函数：根据配置实例化对应的 Provider

    Raises:
        ValueError: 不支持的 protocol
    """
    protocol = config.protocol.lower()

    if protocol == "anthropic":
        from gxcode.provider.anthropic import AnthropicProvider
        return AnthropicProvider(config, tools=tools)

    if protocol == "openai":
        from gxcode.provider.openai import OpenAIProvider
        return OpenAIProvider(config, tools=tools)

    raise ValueError(f"不支持的 protocol: '{config.protocol}'，仅支持 anthropic/openai")