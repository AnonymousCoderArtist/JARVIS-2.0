"""Anthropic LLM Provider implementation using custom SDK"""

from typing import Dict, List, Optional, AsyncGenerator, Union
from .base import BaseLLMProvider
from .sdk_adapter import SDKAdapter
from core.llm_sdk.anthropic.sdk import AnthropicSDK


class AnthropicProvider(SDKAdapter):
    """Anthropic Claude provider implementation using custom SDK"""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        sdk = AnthropicSDK(api_key=api_key, base_url=base_url)
        super().__init__(sdk, "anthropic")
