"""SDK adapter to bridge new SDK pattern with existing agent interface"""

from typing import Dict, List, Optional, AsyncGenerator, Union
from core.llm.base import BaseLLMProvider
from core.llm_sdk.base.sdk import (
    BaseLLMSDK,
    Message,
    GenerationConfig,
    GenerationResponse,
)


class SDKAdapter(BaseLLMProvider):
    """Adapter to make SDK instances compatible with BaseLLMProvider interface"""

    def __init__(self, sdk: BaseLLMSDK, provider_name: str):
        self.sdk = sdk
        self.provider_name = provider_name

    async def generate(
        self,
        messages: List[Dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Union[str, AsyncGenerator]:
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
            # Return generator as-is
            return result
        else:
            # Return content string
            return result.content

    async def generate_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        model: str,
        **kwargs
    ) -> Dict:
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

        # Call SDK
        result = await self.sdk.generate_with_tools(sdk_messages, tools, config)

        # Convert tool calls back to expected format
        tool_calls = []
        if result.tool_calls:
            for tc in result.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    },
                })

        return {
            "content": result.content,
            "tool_calls": tool_calls,
        }

    def get_available_models(self) -> List[str]:
        """Get available models from SDK"""
        return self.sdk.get_available_models()
