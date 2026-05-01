"""Abstract base class for LLM providers"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, TypeAlias

# Type aliases for messages and tool definitions
MessageDict: TypeAlias = dict[str, Any]
ToolDefDict: TypeAlias = dict[str, Any]


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers"""

    @abstractmethod
    async def generate(
        self,
        messages: list[MessageDict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> str | AsyncGenerator[Any, None]:
        """
        Generate a response from the LLM

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name to use
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            str if stream=False, AsyncGenerator if stream=True
        """
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[MessageDict],
        tools: list[ToolDefDict],
        model: str,
        stream: bool = False,
        **kwargs: Any
    ) -> dict[str, Any] | AsyncGenerator[Any, None]:
        """
        Generate a response with tool calling support

        Args:
            messages: List of message dictionaries
            tools: List of tool definitions
            model: Model name to use
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            Dictionary with response and tool calls if any
        """
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """
        Get list of available models for this provider

        Returns:
            List of model names
        """
        pass
