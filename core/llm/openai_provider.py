"""OpenAI LLM Provider implementation using custom SDK"""

from core.llm_sdk.openai.sdk import OpenAISDK

from .sdk_adapter import SDKAdapter


class OpenAIProvider(SDKAdapter):
    """OpenAI GPT provider implementation using custom SDK"""

    def __init__(self, api_key: str, base_url: str | None = None):
        sdk = OpenAISDK(api_key=api_key, base_url=base_url)
        super().__init__(sdk, "openai")
