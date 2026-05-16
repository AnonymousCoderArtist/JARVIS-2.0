"""OpenAI GPT SDK implementation using the official openai package."""

import logging
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk, ChatCompletionToolParam

from ..base.sdk import (
    BaseLLMSDK,
    GenerationConfig,
    GenerationResponse,
    Message,
    ToolCall,
)

logger = logging.getLogger(__name__)


async def _openai_stream_chunks(
    stream: AsyncIterator[ChatCompletionChunk],
) -> AsyncGenerator[dict[str, Any], None]:
    """Convert an OpenAI streaming response into the JARVIS chunk protocol."""
    tool_calls_acc: dict[int, dict[str, Any]] = {}

    async for chunk in stream:
        if chunk.usage:
            yield {"type": "usage", "usage": chunk.usage.model_dump()}

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        reasoning_delta = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning_delta:
            yield {"type": "reasoning", "content": reasoning_delta}
        elif delta.content:
            yield {"type": "text", "content": delta.content}

        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                if tc_delta.id:
                    tool_calls_acc[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        tool_calls_acc[idx]["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments
                    yield {
                        "type": "tool_call",
                        "tool_call": ToolCall(
                            id=tool_calls_acc[idx]["id"],
                            name=tool_calls_acc[idx]["name"],
                            arguments=tool_calls_acc[idx]["arguments"],
                        ),
                    }
    if tool_calls_acc:
        yield {
            "type": "tool_calls",
            "tool_calls": [
                ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"])
                for v in sorted(tool_calls_acc.values(), key=lambda x: x["id"])
            ],
        }


class OpenAISDK(BaseLLMSDK):
    """OpenAI GPT SDK implementation using the official openai package."""

    def __init__(self, api_key: str, base_url: str | None = None):
        super().__init__(api_key, base_url or "https://api.openai.com/v1")
        self.sdk_mode = "messages"
        self._async_client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._async_client

    def _build_kwargs(
        self,
        messages: list[Message],
        config: GenerationConfig,
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        openai_messages = self.convert_messages_to_dict(messages)
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": openai_messages,
        }
        # Only include optional params when they have non-default values
        if config.temperature is not None and config.temperature != 0.7:
            kwargs["temperature"] = config.temperature
        if config.max_tokens is not None:
            kwargs["max_tokens"] = config.max_tokens
        if config.top_p is not None:
            kwargs["top_p"] = config.top_p
        if config.frequency_penalty is not None and config.frequency_penalty != 0.0:
            kwargs["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty is not None and config.presence_penalty != 0.0:
            kwargs["presence_penalty"] = config.presence_penalty
        if config.stop_sequences:
            kwargs["stop"] = config.stop_sequences
        if tools:
            kwargs["tools"] = [
                ChatCompletionToolParam(
                    type="function",
                    function={
                        "name": t["function"]["name"],
                        "description": t["function"].get("description", ""),
                        "parameters": t["function"]["parameters"],
                    },
                )
                for t in tools
            ]
        return kwargs

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        try:
            kwargs = self._build_kwargs(messages, config)
            kwargs["stream"] = stream

            if stream:
                raw_stream = await self.client.chat.completions.create(**kwargs)
                return _openai_stream_chunks(raw_stream)
            else:
                completion = await self.client.chat.completions.create(**kwargs)
                choice = completion.choices[0]
                msg = choice.message
                content = msg.content or ""
                reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", "") or ""

                usage = completion.usage
                return GenerationResponse(
                    content=content,
                    model=completion.model,
                    finish_reason=choice.finish_reason,
                    usage={
                        "input_tokens": usage.prompt_tokens if usage else 0,
                        "output_tokens": usage.completion_tokens if usage else 0,
                        "total_tokens": usage.total_tokens if usage else 0,
                    } if usage else None,
                    reasoning_content=reasoning,
                )

        except Exception as e:
            logger.error(f"OpenAI generation failed: {str(e)}")
            raise RuntimeError(f"OpenAI generation failed: {str(e)}") from e

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        try:
            kwargs = self._build_kwargs(messages, config, tools)
            kwargs["stream"] = stream

            if stream:
                raw_stream = await self.client.chat.completions.create(**kwargs)
                return _openai_stream_chunks(raw_stream)
            else:
                completion = await self.client.chat.completions.create(**kwargs)
                choice = completion.choices[0]
                msg = choice.message
                content = msg.content or ""
                reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", "") or ""

                tool_calls = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(
                            ToolCall(
                                id=tc.id,
                                name=tc.function.name,
                                arguments=tc.function.arguments,
                            )
                        )

                usage = completion.usage
                return GenerationResponse(
                    content=content,
                    model=completion.model,
                    finish_reason=choice.finish_reason,
                    tool_calls=tool_calls or None,
                    usage={
                        "input_tokens": usage.prompt_tokens if usage else 0,
                        "output_tokens": usage.completion_tokens if usage else 0,
                        "total_tokens": usage.total_tokens if usage else 0,
                    } if usage else None,
                    reasoning_content=reasoning,
                )

        except Exception as e:
            logger.error(f"OpenAI tool generation failed: {str(e)}")
            raise RuntimeError(f"OpenAI tool generation failed: {str(e)}") from e

    def get_available_models(self) -> list[str]:
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]

    def convert_messages_to_dict(self, messages: list[Message]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.image_parts:
                content: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
                for image_url in msg.image_parts:
                    content.append({"type": "image_url", "image_url": {"url": image_url}})
                result.append({
                    "role": msg.role,
                    "content": content,
                    **(msg.metadata or {}),
                })
            else:
                result.append({
                    "role": msg.role,
                    "content": msg.content,
                    **(msg.metadata or {}),
                })
        return result
