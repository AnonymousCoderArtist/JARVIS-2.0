"""Provider-specific configuration management"""

from typing import Dict, Optional
from .settings import Settings
from core.llm_sdk.known_providers import (
    KnownProviders,
    get_provider_models,
    get_provider_model_config,
)


class ProviderConfig:
    """Manages provider-specific configurations"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._provider_configs: Dict[str, Dict] = {}

    def get_provider_config(self, provider_name: str) -> Optional[Dict]:
        """
        Get configuration for a specific provider

        Args:
            provider_name: Name of the provider

        Returns:
            Provider configuration dictionary or None if not found
        """
        # Check if provider is known
        known = KnownProviders.get(provider_name)
        if not known:
            return None

        # Get API key and enabled status from config
        api_key = self.settings.get_provider_api_key(provider_name)
        enabled = self.settings.is_provider_enabled(provider_name)

        # Auto-fetch models from known_providers or static list
        models = get_provider_models(provider_name)
        static_config = get_provider_model_config(provider_name)

        config = {
            "id": known.id,
            "display_name": known.display_name,
            "category": known.category.value,
            "sdk_mode": known.sdk_mode.value,
            "base_url": known.base_url,
            "api_key": api_key,
            "enabled": enabled,
            "default_model": known.default_model if known.default_model else (models[0] if models else None),
            "models": models,
            "static_config": static_config,
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        return config

    def set_provider_config(self, provider_name: str, config: Dict):
        """
        Set configuration for a provider

        Args:
            provider_name: Name of the provider
            config: Configuration dictionary
        """
        self._provider_configs[provider_name] = config

    def list_configured_providers(self) -> list[str]:
        """
        List all configured providers

        Returns:
            List of provider names
        """
        return list(KnownProviders.keys())

    def list_enabled_providers(self) -> list[str]:
        """
        List all enabled providers

        Returns:
            List of provider names
        """
        return [
            provider_id
            for provider_id in self.list_configured_providers()
            if self.settings.is_provider_enabled(provider_id)
        ]

    def update_provider_model(self, provider_name: str, model: str):
        """
        Update the model for a provider

        Args:
            provider_name: Name of the provider
            model: New model name
        """
        # Update selected model in config
        self.settings.set("model", "selected", {"id": model})
        self.settings.save()

    def get_default_provider(self) -> Optional[str]:
        """
        Get the default provider name

        Returns:
            Default provider name or None if not configured
        """
        selected = self.settings.selected_provider_id
        if selected and self.settings.is_provider_enabled(selected):
            return selected

        # Find first enabled provider
        for provider_id in self.list_configured_providers():
            if self.settings.is_provider_enabled(provider_id):
                return provider_id

        return None

    def get_provider_model(self, provider_name: str) -> str:
        """Get the configured model for a provider"""
        # First check if model is selected in config
        selected_model = self.settings.selected_model_id
        if selected_model and provider_name == self.settings.selected_provider_id:
            return selected_model

        # Otherwise get from provider config
        config = self.get_provider_config(provider_name)
        if config:
            return config.get("default_model", "default")
        return "default"

    def set_provider_model(self, provider_name: str, model: str):
        """Set the model for a provider"""
        # Update selected model in config
        self.settings.set("model", "selected", {"id": model})
        self.settings.save()
