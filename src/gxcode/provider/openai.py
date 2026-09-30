"""OpenAI Provider

通过 Chat Completions API (streaming) 调用 OpenAI 模型。
支持 tool_calls 工具调用。

文档: https://platform.openai.com/docs/api-reference/chat/create
"""

import json
from typing import AsyncIterator

import httpx

from gxcode.config import ProviderConfig
from gxcode.provider import Provider
from gxcode.types_ import ErrorEvent, Message, StreamEvent, TextDelta, TokenUsage, ToolCall, UsageEvent


class OpenAIProvider(Provider):
    """OpenAI Chat Completions 流式 Provider"""

    def __init__(self, config: ProviderConfig, tools: list[dict] | None = None):
        self._config = config
        self._tools = tools

    async def stream_chat(
        self,
        messages: list[Message],
        model: str,
        **options
    ) -> AsyncIterator[StreamEvent]:
        """流式调用 OpenAI Chat Completions API"""
        body: dict = {
            "model": model,
            "messages": _to_api_messages(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        # tools
        if self._tools:
            body["tools"] = self._tools

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
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
                        yield ErrorEvent(message=f"OpenAI API 错误 ({response.status_code}): {error_text.decode()[:500]}")
                        return

                    # 工具调用累积
                    tool_calls_map: dict[int, dict] = {}  # index -> {id, name, arguments_str}

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

                        # usage（流式最后一个 chunk 可能携带，值可能为 null）
                        if "usage" in data:
                            u = data["usage"] or {}
                            prompt = u.get("prompt_tokens", 0)
                            completion = u.get("completion_tokens", 0)
                            if prompt or completion:
                                yield UsageEvent(usage=TokenUsage(
                                    prompt_tokens=prompt,
                                    completion_tokens=completion,
                                ))

                        choices = data.get("choices", [])
                        if not choices:
                            continue

                        # choices[0] 或 delta 可能为 null（API 偶发），用 or {} 兜底
                        choice = choices[0]
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta") or {}
                        finish_reason = choice.get("finish_reason")

                        # 文本内容
                        content = delta.get("content", "")
                        if content:
                            yield TextDelta(content=content)

                        # 工具调用
                        tool_calls = delta.get("tool_calls", [])
                        for tc in tool_calls:
                            if not isinstance(tc, dict):
                                continue
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments_str": "",
                                }
                            entry = tool_calls_map[idx]
                            if "id" in tc and tc["id"]:
                                entry["id"] = tc["id"]
                            func = tc.get("function") or {}
                            if "name" in func and func["name"]:
                                entry["name"] = func["name"]
                            if "arguments" in func:
                                entry["arguments_str"] += func["arguments"]

                        # 工具调用完成时产出 ToolCall
                        if finish_reason == "tool_calls" or finish_reason == "stop":
                            for entry in tool_calls_map.values():
                                if entry["name"] and entry["arguments_str"]:
                                    try:
                                        arguments = json.loads(entry["arguments_str"])
                                        yield ToolCall(
                                            tool_id=entry["id"],
                                            name=entry["name"],
                                            arguments=arguments,
                                        )
                                    except json.JSONDecodeError:
                                        yield ErrorEvent(message=f"工具参数 JSON 解析失败: {entry['arguments_str'][:200]}")

        except httpx.HTTPError as e:
            yield ErrorEvent(message=f"网络错误: {e}")
        except Exception as e:
            yield ErrorEvent(message=f"未知错误: {e}")


def _to_api_messages(messages: list[Message]) -> list[dict]:
    """把内部 Message 列表序列化为 OpenAI Chat Completions 消息格式

    - assistant 消息携带原生 tool_calls 字段（不再拼文本摘要，
      避免模型模仿文本形式的调用而不走 function calling）
    - 工具结果用 role="tool" + tool_call_id 回灌，与 assistant.tool_calls 配对
    - 配对保护：
      * 孤儿工具结果（前面没有对应的 assistant.tool_calls）降级为 user 文本，
        避免 API 400（历史被压缩/截断后可能出现）
      * assistant.tool_calls 后缺少工具响应时，自动合成占位响应补齐配对
    """
    out: list[dict] = []
    pending_ids: list[str] = []  # 尚未收到响应的 tool_call id

    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            # 先补齐上一条 assistant 未应答的调用（防御历史损坏）
            _flush_pending(out, pending_ids)
            ids = [tc.get("id", "") for tc in m.tool_calls if tc.get("id")]
            out.append({
                "role": "assistant",
                "content": m.content or None,
                "tool_calls": m.tool_calls,
            })
            pending_ids = list(ids)
        elif m.role == "tool":
            if m.tool_call_id and m.tool_call_id in pending_ids:
                pending_ids.remove(m.tool_call_id)
                out.append({
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content,
                })
            else:
                # 孤儿工具结果：降级为 user 文本（兼容压缩/恢复后的历史）
                out.append({
                    "role": "user",
                    "content": f"[tool_result from {m.name or 'tool'}]\n{m.content}",
                })
        else:
            _flush_pending(out, pending_ids)
            pending_ids = []
            out.append({"role": m.role, "content": m.content})

    _flush_pending(out, pending_ids)
    return out


def _flush_pending(out: list[dict], pending_ids: list[str]) -> None:
    """为未应答的 tool_call 合成占位响应，保证配对完整"""
    for tid in pending_ids:
        out.append({
            "role": "tool",
            "tool_call_id": tid,
            "content": "(此调用的结果因上下文压缩而丢失，如需详情请重新调用工具)",
        })
    pending_ids.clear()