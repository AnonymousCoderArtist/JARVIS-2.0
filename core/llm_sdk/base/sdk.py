"""Base SDK class for LLM providers"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SdkMode(Enum):
    """SDK mode for different API styles"""
    STANDARD = "standard"
    STREAMING = "streaming"
    MESSAGES = "messages"
    COMPLETIONS = "completions"


@dataclass
class Message:
    """Message for LLM conversation"""
    role: str
    content: str
    metadata: dict[str, Any] | None = None


@dataclass
class GenerationConfig:
    """Configuration for text generation"""
    model: str
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop_sequences: list[str] | None = None


@dataclass
class ToolCall:
    """Tool call from LLM"""
    id: str
    name: str
    arguments: str


@dataclass
class GenerationResponse:
    """Response from text generation"""
    content: str
    model: str
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: dict[str, int] | None = None
    metadata: dict[str, Any] | None = None
    reasoning_content: str = ""  # For models with reasoning/thinking content


class BaseLLMSDK(ABC):
    """Base class for LLM SDK implementations"""

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    @property
    @abstractmethod
    def client(self):
        """Lazy load the SDK client"""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        """
        Generate text response

        Args:
            messages: List of conversation messages
            config: Generation configuration
            stream: Whether to stream the response

        Returns:
            GenerationResponse or AsyncGenerator if streaming
        """
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> GenerationResponse | AsyncGenerator:
        """
        Generate response with tool calling

        Args:
            messages: List of conversation messages
            tools: List of tool definitions
            config: Generation configuration
            stream: Whether to stream the response

        Returns:
            GenerationResponse or AsyncGenerator if streaming
        """
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """Get list of available models"""
        pass

    def convert_messages_to_dict(self, messages: list[Message]) -> list[dict]:
        """Convert Message objects to dictionaries"""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                **(msg.metadata or {})
            }
            for msg in messages
        ]

    def convert_dict_to_messages(self, messages: list[dict]) -> list[Message]:
        """Convert dictionaries to Message objects"""
        return [
            Message(
                role=msg["role"],
                content=msg["content"],
                metadata={k: v for k, v in msg.items() if k not in ["role", "content"]}
            )
            for msg in messages
        ]
