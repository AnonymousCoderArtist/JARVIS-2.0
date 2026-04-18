"""Anthropic LLM Provider implementation using custom SDK"""

from core.llm_sdk.anthropic.sdk import AnthropicSDK

from .sdk_adapter import SDKAdapter


class AnthropicProvider(SDKAdapter):
    """Anthropic Claude provider implementation using custom SDK"""

    def __init__(self, api_key: str, base_url: str | None = None):
        sdk = AnthropicSDK(api_key=api_key, base_url=base_url)
        super().__init__(sdk, "anthropic")
