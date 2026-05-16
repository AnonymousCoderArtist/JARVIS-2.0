"""Anthropic Claude SDK implementation using the official anthropic package."""

import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import MessageStreamEvent, ToolUseBlock, Usage

from ..base.sdk import (
    BaseLLMSDK,
    GenerationConfig,
    GenerationResponse,
    Message,
    ToolCall,
)

logger = logging.getLogger(__name__)


async def _anthropic_stream_chunks(
    stream: AsyncIterator[MessageStreamEvent],
) -> AsyncGenerator[dict[str, Any], None]:
    """Convert an Anthropic streaming response into the JARVIS chunk protocol."""
    content_buffer = ""
    current_tool: dict[str, Any] | None = None

    async for event in stream:
        if event.type == "content_block_start":
            block = getattr(event, "content_block", None)
            if block is not None and isinstance(block, ToolUseBlock):
                current_tool = {"id": block.id, "name": block.name, "arguments": ""}

        elif event.type == "content_block_delta":
            delta = getattr(event, "delta", None)
            if delta is not None:
                delta_type = getattr(delta, "type", "")
                if delta_type == "text_delta":
                    text = getattr(delta, "text", "")
                    content_buffer += text
                    yield {"type": "text", "content": text}
                elif delta_type == "thinking_delta":
                    yield {"type": "reasoning", "content": getattr(delta, "thinking", "")}
                elif delta_type == "input_json_delta" and current_tool is not None:
                    current_tool["arguments"] += getattr(delta, "partial_json", "")

        elif event.type == "content_block_stop":
            if current_tool is not None:
                tc = ToolCall(
                    id=current_tool["id"],
                    name=current_tool["name"],
                    arguments=current_tool["arguments"],
                )
                yield {"type": "tool_call", "tool_call": tc}
                current_tool = None

        elif event.type == "message_delta":
            usage = getattr(event, "usage", None)
            if usage is not None:
                yield {"type": "usage", "usage": usage.model_dump()}

        elif event.type == "message_stop":
            break


class AnthropicSDK(BaseLLMSDK):
    """Anthropic Claude SDK implementation using the official anthropic package."""

    def __init__(self, api_key: str, base_url: str | None = None):
        super().__init__(api_key, base_url or "https://api.anthropic.com/v1")
        self.sdk_mode = "messages"
        self._async_client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._async_client is None:
            self._async_client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._async_client

    def _build_messages_and_system(
        self, messages: list[Message]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split messages into Anthropic messages array and system prompt.

        Applies prompt caching to system prompt, tools, and last user message.
        """
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                content = msg.content
                if msg.image_parts:
                    blocks: list[dict[str, Any]] = [{"type": "text", "text": content}]
                    for img in msg.image_parts:
                        blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img,
                            },
                        })
                    content = blocks
                anthropic_messages.append({"role": msg.role, "content": content})

        system_text = "\n".join(system_parts)

        # Apply prompt caching to system prompt
        if system_text:
            system_payload: list[dict[str, Any]] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]
        else:
            system_payload = []

        # Apply prompt caching to last user message
        for i in range(len(anthropic_messages) - 1, -1, -1):
            msg = anthropic_messages[i]
            if msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, str) and content:
                    msg["content"] = [
                        {"type": "text", "text": content},
                        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
                    ]
                elif isinstance(content, list) and content:
                    content[-1]["cache_control"] = {"type": "ephemeral"}
                break

        return anthropic_messages, system_payload

    def _build_tools(self, tools: list[dict]) -> list[dict[str, Any]]:
        """Convert JARVIS tool definitions to Anthropic format with caching."""
        if not tools:
            return []
        anthropic_tools: list[dict[str, Any]] = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]
        # Cache the last tool definition
        anthropic_tools[-1] = {**anthropic_tools[-1], "cache_control": {"type": "ephemeral"}}
        return anthropic_tools

    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        try:
            anthropic_messages, system_payload = self._build_messages_and_system(messages)

            kwargs: dict[str, Any] = {
                "model": config.model,
                "messages": anthropic_messages,
                "max_tokens": config.max_tokens or 4096,
                "temperature": config.temperature,
            }
            if system_payload:
                kwargs["system"] = system_payload

            if stream:
                raw_stream = await self.client.messages.create(**kwargs, stream=True)
                return _anthropic_stream_chunks(raw_stream)
            else:
                msg = await self.client.messages.create(**kwargs)
                content = ""
                reasoning = ""
                for block in msg.content:
                    if block.type == "text":
                        content += block.text
                    elif block.type == "thinking":
                        reasoning += block.thinking

                usage: Usage = msg.usage  # type: ignore
                return GenerationResponse(
                    content=content,
                    model=msg.model,
                    finish_reason=msg.stop_reason,
                    usage=usage.model_dump() if usage else None,
                    reasoning_content=reasoning,
                )

        except Exception as e:
            logger.error(f"Anthropic generation failed: {str(e)}")
            raise RuntimeError(f"Anthropic generation failed: {str(e)}") from e

    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        try:
            anthropic_messages, system_payload = self._build_messages_and_system(messages)

            kwargs: dict[str, Any] = {
                "model": config.model,
                "messages": anthropic_messages,
                "tools": self._build_tools(tools),
                "max_tokens": config.max_tokens or 4096,
                "temperature": config.temperature,
            }
            if system_payload:
                kwargs["system"] = system_payload

            if stream:
                raw_stream = await self.client.messages.create(**kwargs, stream=True)
                return _anthropic_stream_chunks(raw_stream)
            else:
                msg = await self.client.messages.create(**kwargs)
                content = ""
                reasoning = ""
                tool_calls = []
                for block in msg.content:
                    if block.type == "text":
                        content += block.text
                    elif block.type == "thinking":
                        reasoning += block.thinking
                    elif block.type == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block.id,
                                name=block.name,
                                arguments=json.dumps(block.input),
                            )
                        )

                usage: Usage = msg.usage  # type: ignore
                return GenerationResponse(
                    content=content,
                    model=msg.model,
                    finish_reason=msg.stop_reason,
                    tool_calls=tool_calls or None,
                    usage=usage.model_dump() if usage else None,
                    reasoning_content=reasoning,
                )

        except Exception as e:
            logger.error(f"Anthropic tool generation failed: {str(e)}")
            raise RuntimeError(f"Anthropic tool generation failed: {str(e)}") from e

    def get_available_models(self) -> list[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]

    def convert_messages_to_dict(self, messages: list[Message]) -> list[dict]:
        return [
            {"role": msg.role, "content": msg.content, **(msg.metadata or {})}
            for msg in messages
        ]
