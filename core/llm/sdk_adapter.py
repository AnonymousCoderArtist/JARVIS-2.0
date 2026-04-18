"""SDK adapter to bridge new SDK pattern with existing agent interface"""

from collections.abc import AsyncGenerator
from typing import cast

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
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | AsyncGenerator:
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
            return cast(AsyncGenerator, result)
        else:
            # SDK returns a GenerationResponse when not streaming; cast and return content
            gen = cast(GenerationResponse, result)
            return gen.content

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str,
        **kwargs
    ) -> dict | AsyncGenerator:
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

        stream = kwargs.get("stream", False)

        # Call SDK
        result = await self.sdk.generate_with_tools(sdk_messages, tools, config, stream=stream)

        if stream:
            return cast(AsyncGenerator, result)
        else:
            # Convert tool calls back to expected format
            gen = cast(GenerationResponse, result)
            tool_calls = []
            if gen.tool_calls:
                for tc in gen.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    })

            return {
                "content": gen.content,
                "tool_calls": tool_calls,
            }

    def get_available_models(self) -> list[str]:
        """Get available models from SDK"""
        return self.sdk.get_available_models()
