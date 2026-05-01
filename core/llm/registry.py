"""LLM Provider Registry for managing multiple providers"""

from core.provider import ProviderManager
from .base import BaseLLMProvider
from .sdk_adapter import SDKAdapter


class LLMProviderRegistry:
    """Registry for managing LLM providers using dynamic configuration"""

    def __init__(self, config_path: str | None = None):
        self._providers: dict[str, BaseLLMProvider] = {}
        self._provider_manager = ProviderManager(config_path)

    def register(self, name: str, provider: BaseLLMProvider):
        """
        Register an LLM provider instance

        Args:
            name: Name to register the provider under
            provider: Provider instance
        """
        self._providers[name] = provider

    def get(self, name: str) -> BaseLLMProvider | None:
        """
        Get a registered provider by name

        Args:
            name: Provider name

        Returns:
            Provider instance or None if not found
        """
        # Check if already instantiated
        if name in self._providers:
            return self._providers[name]

        # Try to create from dynamic provider configuration
        provider_config = self._provider_manager.get_provider(name)
        if provider_config and provider_config.enabled:
            sdk_instance = self._provider_manager.create_sdk_instance(name)
            if sdk_instance:
                provider = SDKAdapter(sdk_instance, name)
                self._providers[name] = provider
                return provider

        return None

    def list_providers(self) -> list[str]:
        """
        List all available provider names

        Returns:
            List of provider names
        """
        # Combine registered and configured providers
        configured = [p.provider_id for p in self._provider_manager.list_providers()]
        registered = list(self._providers.keys())
        return list(set(configured + registered))

    def list_enabled_providers(self) -> list[str]:
        """
        List all enabled provider names

        Returns:
            List of enabled provider names
        """
        return [p.provider_id for p in self._provider_manager.list_enabled_providers()]

    def get_provider_manager(self) -> ProviderManager:
        """
        Get the underlying provider manager

        Returns:
            ProviderManager instance
        """
        return self._provider_manager
