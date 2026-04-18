"""Abstract base class for LLM providers"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator, Union


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers"""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Union[str, AsyncGenerator]:
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
        messages: List[Dict],
        tools: List[Dict],
        model: str,
        **kwargs
    ) -> Dict:
        """
        Generate a response with tool calling support

        Args:
            messages: List of message dictionaries
            tools: List of tool definitions
            model: Model name to use
            **kwargs: Additional parameters

        Returns:
            Dictionary with response and tool calls if any
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """
        Get list of available models for this provider

        Returns:
            List of model names
        """
        pass
