"""SDK adapter to bridge new SDK pattern with existing agent interface"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, cast

from core.llm.base import BaseLLMProvider
from core.llm_sdk.base.sdk import (
    BaseLLMSDK,
    GenerationConfig,
    Message,
    GenerationResponse,
)


class SDKAdapter(BaseLLMProvider):
    """Adapter to make SDK instances compatible with BaseLLMProvider interface"""

    def __init__(self, sdk: BaseLLMSDK, provider_name: str):
        self.sdk = sdk
        self.provider_name = provider_name

    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | AsyncGenerator[Any, None]:
        """Generate using SDK with adapter interface"""
        # Convert dict messages to SDK Message objects, filtering out empty messages
        sdk_messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
            if msg.get("content") or msg.get("role") == "system"
        ]

        # Create generation config
        config = GenerationConfig(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Call SDK
        result = await self.sdk.generate(sdk_messages, config, stream)

        if stream:
            # SDK returns an AsyncGenerator when streaming; return as-is
            return cast(AsyncGenerator[Any, None], result)
        else:
            # SDK returns a GenerationResponse when not streaming; return content
            gen = cast(GenerationResponse, result)
            return gen.content

    def _generation_response_to_dict(self, gen: GenerationResponse) -> dict[str, Any]:
        """Convert a typed SDK response into the mapping shape expected by agents."""
        tool_calls: list[dict[str, Any]] = []
        if gen.tool_calls:
            for tc in gen.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                )

        response: dict[str, Any] = {
            "content": gen.content,
            "model": gen.model,
            "finish_reason": gen.finish_reason,
            "reasoning_content": gen.reasoning_content or "",
        }

        if tool_calls:
            response["tool_calls"] = tool_calls
        if gen.usage is not None:
            response["usage"] = gen.usage
        if gen.metadata is not None:
            response["metadata"] = gen.metadata

        return response

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncGenerator[Any, None]:
        """Generate with tools using SDK with adapter interface"""
        # Convert dict messages to SDK Message objects, filtering out empty messages
        sdk_messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
            if msg.get("content") or msg.get("role") == "system"
        ]

        # Create generation config
        config = GenerationConfig(
            model=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
        )

        stream = kwargs.pop("stream", stream)

        # Call SDK
        result = await self.sdk.generate_with_tools(sdk_messages, tools, config, stream=stream)

        if stream:
            return cast(AsyncGenerator[Any, None], result)
        else:
            gen = cast(GenerationResponse, result)
            return self._generation_response_to_dict(gen)

    def get_available_models(self) -> list[str]:
        """Get available models from SDK"""
        return self.sdk.get_available_models()