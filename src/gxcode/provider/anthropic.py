"""Anthropic Claude Provider

通过 Messages API (streaming) 调用 Anthropic Claude 模型。
支持 extended thinking 和 tool_use 工具调用。

文档: https://docs.anthropic.com/en/api/messages-streaming
"""

import json
from typing import AsyncIterator

import httpx

from gxcode.config import ProviderConfig
from gxcode.provider import Provider
from gxcode.types_ import ErrorEvent, Message, StreamEvent, TextDelta, ThinkingDelta, TokenUsage, ToolCall, UsageEvent


class AnthropicProvider(Provider):
    """Anthropic Messages API 流式 Provider"""

    def __init__(self, config: ProviderConfig, tools: list[dict] | None = None):
        self._config = config
        self._tools = tools

    async def stream_chat(
        self,
        messages: list[Message],
        model: str,
        **options
    ) -> AsyncIterator[StreamEvent]:
        """流式调用 Anthropic Messages API"""
        body: dict = {
            "model": model,
            "messages": [_legacy_content(m) for m in messages],
            "stream": True,
            "max_tokens": 4096,
        }

        # extended thinking
        if options.get("thinking", False):
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": 4000,
            }

        # tools
        if self._tools:
            body["tools"] = self._tools

        headers = {
            "x-api-key": self._config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    self._config.base_url,
                    json=body,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield ErrorEvent(message=f"Anthropic API 错误 ({response.status_code}): {error_text.decode()[:500]}")
                        return

                    # 工具调用状态
                    current_tool_id: str | None = None
                    current_tool_name: str | None = None
                    current_tool_json: str = ""

                    # usage 累积
                    input_tokens = 0
                    output_tokens = 0

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            return

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # json.loads("null") 返回 None，不会触发 JSONDecodeError，需显式守卫
                        if not isinstance(data, dict):
                            continue

                        event_type = data.get("type", "")

                        # content_block_start: 新内容块开始
                        if event_type == "content_block_start":
                            content_block = data.get("content_block", {})
                            if content_block.get("type") == "tool_use":
                                current_tool_id = content_block.get("id", "")
                                current_tool_name = content_block.get("name", "")
                                current_tool_json = ""

                        # message_start: 捕获 input_tokens
                        elif event_type == "message_start":
                            msg = data.get("message") or {}
                            usage_data = msg.get("usage") or {}
                            input_tokens = usage_data.get("input_tokens", 0)

                        # message_delta: 捕获 output_tokens
                        elif event_type == "message_delta":
                            usage_data = data.get("usage") or {}
                            output_tokens = usage_data.get("output_tokens", 0)

                        # content_block_delta: 增量内容
                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            delta_type = delta.get("type", "")

                            if delta_type == "text_delta":
                                yield TextDelta(content=delta.get("text", ""))
                            elif delta_type == "thinking_delta":
                                yield ThinkingDelta(content=delta.get("thinking", ""))
                            elif delta_type == "input_json_delta":
                                current_tool_json += delta.get("partial_json", "")

                        # content_block_stop: 内容块结束
                        elif event_type == "content_block_stop":
                            if current_tool_id and current_tool_json:
                                try:
                                    arguments = json.loads(current_tool_json)
                                    yield ToolCall(
                                        tool_id=current_tool_id,
                                        name=current_tool_name or "",
                                        arguments=arguments,
                                    )
                                except json.JSONDecodeError:
                                    yield ErrorEvent(message=f"工具参数 JSON 解析失败: {current_tool_json[:200]}")
                            current_tool_id = None
                            current_tool_name = None
                            current_tool_json = ""

                        # 错误事件
                        elif event_type == "error":
                            err = data.get("error", {})
                            yield ErrorEvent(message=f"Anthropic 错误: {err.get('message', str(data))}")

                        # message_stop: 流结束，产出 usage
                        elif event_type == "message_stop":
                            if input_tokens or output_tokens:
                                yield UsageEvent(usage=TokenUsage(
                                    prompt_tokens=input_tokens,
                                    completion_tokens=output_tokens,
                                ))

        except httpx.HTTPError as e:
            yield ErrorEvent(message=f"网络错误: {e}")
        except Exception as e:
            yield ErrorEvent(message=f"未知错误: {e}")


def _legacy_content(m: Message) -> dict:
    """降级序列化：tool 消息转回 user 文本，assistant 原生 tool_calls 忽略

    Anthropic 协议此前的实现就是纯文本回灌（[tool_result from X] 用户消息），
    这里保持等价行为，避免新消息格式破坏 Claude 供应商。
    """
    if m.role == "tool":
        return {
            "role": "user",
            "content": f"[tool_result from {m.name or 'tool'}]\n{m.content}",
        }
    return {"role": m.role, "content": m.content}