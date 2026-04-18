"""Base SDK class for LLM providers"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator, Union, Any
from dataclasses import dataclass
from enum import Enum


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
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class GenerationConfig:
    """Configuration for text generation"""
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None


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
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLMSDK(ABC):
    """Base class for LLM SDK implementations"""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
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
        messages: List[Message],
        config: GenerationConfig,
        stream: bool = False,
    ) -> Union[GenerationResponse, AsyncGenerator]:
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
        messages: List[Message],
        tools: List[Dict],
        config: GenerationConfig,
        stream: bool = False,
    ) -> Union[GenerationResponse, AsyncGenerator]:
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
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        pass

    def convert_messages_to_dict(self, messages: List[Message]) -> List[Dict]:
        """Convert Message objects to dictionaries"""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                **(msg.metadata or {})
            }
            for msg in messages
        ]

    def convert_dict_to_messages(self, messages: List[Dict]) -> List[Message]:
        """Convert dictionaries to Message objects"""
        return [
            Message(
                role=msg["role"],
                content=msg["content"],
                metadata={k: v for k, v in msg.items() if k not in ["role", "content"]}
            )
            for msg in messages
        ]
