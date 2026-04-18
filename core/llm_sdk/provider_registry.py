"""Provider registry system for managing LLM SDKs"""

from typing import Dict, Optional, Type, List, Any
from dataclasses import dataclass, field
from .base.sdk import BaseLLMSDK, GenerationConfig, Message
from .known_providers import KnownProviders, KnownProviderConfig, get_known_provider, ProviderCategory


@dataclass
class ProviderConfig:
    """Configuration for a provider"""
    id: str
    name: str
    category: ProviderCategory
    api_key_env_var: str
    base_url_env_var: Optional[str] = None
    default_model: str = ""
    models: List[str] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_second: int = 1
    window_ms: int = 1000


class ProviderRegistry:
    """Registry for managing LLM providers"""

    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._sdk_instances: Dict[str, BaseLLMSDK] = {}
        self._rate_limits: Dict[str, RateLimitConfig] = {}
        self._initialize_from_known_providers()

    def _initialize_from_known_providers(self):
        """Initialize providers from known_providers.py"""
        for provider_id, known_config in KnownProviders.items():
            # Convert KnownProviderConfig to ProviderConfig
            provider_config = ProviderConfig(
                id=known_config.id,
                name=known_config.display_name,
                category=known_config.category,
                api_key_env_var=known_config.api_key_env_var,
                base_url_env_var=known_config.base_url,
                default_model=known_config.default_model,
                models=known_config.models,
                enabled=True,
                metadata={
                    "sdk_mode": known_config.sdk_mode.value,
                    "fetch_models": known_config.fetch_models,
                    "models_endpoint": known_config.models_endpoint,
                    "max_input_tokens": known_config.max_input_tokens,
                    "max_output_tokens": known_config.max_output_tokens,
                    "total_context_tokens": known_config.total_context_tokens,
                    **known_config.metadata
                }
            )
            self._providers[provider_id] = provider_config
            
            # Register rate limits if configured
            if known_config.rate_limit:
                if known_config.rate_limit.default:
                    self._rate_limits[provider_id] = known_config.rate_limit.default
                elif known_config.rate_limit.openai and known_config.sdk_mode.value == "openai":
                    self._rate_limits[provider_id] = known_config.rate_limit.openai
                elif known_config.rate_limit.anthropic and known_config.sdk_mode.value == "anthropic":
                    self._rate_limits[provider_id] = known_config.rate_limit.anthropic

    def register_provider_config(self, config: ProviderConfig):
        """
        Register a provider configuration

        Args:
            config: Provider configuration
        """
        self._providers[config.id] = config

    def get_provider_config(self, provider_id: str) -> Optional[ProviderConfig]:
        """
        Get provider configuration by ID

        Args:
            provider_id: Provider ID

        Returns:
            Provider configuration or None
        """
        return self._providers.get(provider_id)

    def list_providers(self) -> List[ProviderConfig]:
        """
        List all registered providers

        Returns:
            List of provider configurations
        """
        return list(self._providers.values())

    def get_enabled_providers(self) -> List[ProviderConfig]:
        """
        Get all enabled providers

        Returns:
            List of enabled provider configurations
        """
        return [p for p in self._providers.values() if p.enabled]

    def enable_provider(self, provider_id: str):
        """
        Enable a provider

        Args:
            provider_id: Provider ID
        """
        if provider_id in self._providers:
            self._providers[provider_id].enabled = True

    def disable_provider(self, provider_id: str):
        """
        Disable a provider

        Args:
            provider_id: Provider ID
        """
        if provider_id in self._providers:
            self._providers[provider_id].enabled = False

    def get_sdk_instance(
        self,
        provider_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Optional[BaseLLMSDK]:
        """
        Get or create an SDK instance for a provider

        Args:
            provider_id: Provider ID
            api_key: API key (optional, will use config default if not provided)
            base_url: Base URL (optional, will use config default if not provided)

        Returns:
            SDK instance or None
        """
        config = self.get_provider_config(provider_id)
        if not config:
            return None

        # Use base_url from config if not provided
        if not base_url:
            base_url = config.base_url_env_var

        # Return cached instance if available
        cache_key = f"{provider_id}:{api_key or 'default'}:{base_url or 'default'}"
        if cache_key in self._sdk_instances:
            return self._sdk_instances[cache_key]

        # Create new SDK instance
        sdk = self._create_sdk_instance(config, api_key, base_url)
        if sdk:
            self._sdk_instances[cache_key] = sdk

        return sdk

    def _create_sdk_instance(
        self,
        config: ProviderConfig,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> Optional[BaseLLMSDK]:
        """Create an SDK instance based on provider category"""
        try:
            if config.category == ProviderCategory.ANTHROPIC:
                from .anthropic.sdk import AnthropicSDK
                return AnthropicSDK(api_key or "", base_url)
            elif config.category == ProviderCategory.OPENAI:
                from .openai.sdk import OpenAISDK
                return OpenAISDK(api_key or "", base_url)
            elif config.id == "copilot":
                from .copilot.sdk import CopilotSDK
                return CopilotSDK(github_token=api_key, base_url=base_url)
            else:
                return None
        except Exception as e:
            print(f"Error creating SDK instance for {config.id}: {e}")
            return None

    def set_rate_limit(self, provider_id: str, rate_limit: RateLimitConfig):
        """
        Set rate limit for a provider

        Args:
            provider_id: Provider ID
            rate_limit: Rate limit configuration
        """
        self._rate_limits[provider_id] = rate_limit

    def get_rate_limit(self, provider_id: str) -> Optional[RateLimitConfig]:
        """
        Get rate limit for a provider

        Args:
            provider_id: Provider ID

        Returns:
            Rate limit configuration or None
        """
        return self._rate_limits.get(provider_id)

    def clear_sdk_cache(self):
        """Clear cached SDK instances"""
        self._sdk_instances.clear()

    def reload_known_providers(self):
        """Reload all providers from known_providers.py"""
        self._providers.clear()
        self._rate_limits.clear()
        self._initialize_from_known_providers()

    def add_known_provider(self, provider_id: str):
        """
        Add a single provider from known_providers to the registry
        
        Args:
            provider_id: Provider ID to add
        """
        known_config = get_known_provider(provider_id)
        if known_config:
            provider_config = ProviderConfig(
                id=known_config.id,
                name=known_config.display_name,
                category=known_config.category,
                api_key_env_var=known_config.api_key_env_var,
                base_url_env_var=known_config.base_url,
                default_model=known_config.default_model,
                models=known_config.models,
                enabled=True,
                metadata={
                    "sdk_mode": known_config.sdk_mode.value,
                    "fetch_models": known_config.fetch_models,
                    "models_endpoint": known_config.models_endpoint,
                    "max_input_tokens": known_config.max_input_tokens,
                    "max_output_tokens": known_config.max_output_tokens,
                    "total_context_tokens": known_config.total_context_tokens,
                    **known_config.metadata
                }
            )
            self._providers[provider_id] = provider_config


# Global registry instance
provider_registry = ProviderRegistry()
