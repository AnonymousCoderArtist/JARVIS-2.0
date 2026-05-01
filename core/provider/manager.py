"""Dynamic provider manager for user-configurable LLM providers"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import ProviderConfig, SdkMode


class ProviderManager:
    """Manager for dynamic provider configuration"""

    def __init__(self, config_path: str | None = None):
        self._providers: dict[str, ProviderConfig] = {}
        self._config_path = config_path
        self._load_providers()

    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Check common config locations
        config_paths = [
            "providers.json",
            os.path.expanduser("~/.jarvis/providers.json"),
            os.path.expanduser("~/.config/jarvis/providers.json"),
        ]
        for path in config_paths:
            if os.path.exists(path):
                return path
        return "providers.json"

    def _load_providers(self):
        """Load providers from configuration file"""
        config_path = self._config_path or self._get_default_config_path()
        
        if not os.path.exists(config_path):
            # Create default config file
            self._config_path = config_path
            self._save_providers()
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for provider_id, provider_data in data.items():
                self._providers[provider_id] = ProviderConfig.from_dict(provider_data)
        except Exception as e:
            print(f"Error loading providers: {e}")
            self._providers = {}

    def _save_providers(self):
        """Save providers to configuration file"""
        if not self._config_path:
            self._config_path = self._get_default_config_path()
            
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(self._config_path)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)

            data = {
                provider_id: config.to_dict()
                for provider_id, config in self._providers.items()
            }

            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving providers: {e}")

    def add_provider(self, config: ProviderConfig) -> bool:
        """
        Add or update a provider configuration

        Args:
            config: Provider configuration

        Returns:
            True if successful, False otherwise
        """
        self._providers[config.provider_id] = config
        self._save_providers()
        return True

    def remove_provider(self, provider_id: str) -> bool:
        """
        Remove a provider configuration

        Args:
            provider_id: Provider ID to remove

        Returns:
            True if successful, False otherwise
        """
        if provider_id in self._providers:
            del self._providers[provider_id]
            self._save_providers()
            return True
        return False

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        """
        Get a provider configuration

        Args:
            provider_id: Provider ID

        Returns:
            Provider configuration or None
        """
        return self._providers.get(provider_id)

    def list_providers(self) -> list[ProviderConfig]:
        """
        List all provider configurations

        Returns:
            List of provider configurations
        """
        return list(self._providers.values())

    def list_enabled_providers(self) -> list[ProviderConfig]:
        """
        List enabled provider configurations

        Returns:
            List of enabled provider configurations
        """
        return [p for p in self._providers.values() if p.enabled]

    def enable_provider(self, provider_id: str) -> bool:
        """
        Enable a provider

        Args:
            provider_id: Provider ID

        Returns:
            True if successful, False otherwise
        """
        if provider_id in self._providers:
            self._providers[provider_id].enabled = True
            self._save_providers()
            return True
        return False

    def disable_provider(self, provider_id: str) -> bool:
        """
        Disable a provider

        Args:
            provider_id: Provider ID

        Returns:
            True if successful, False otherwise
        """
        if provider_id in self._providers:
            self._providers[provider_id].enabled = False
            self._save_providers()
            return True
        return False

    def get_default_provider(self) -> ProviderConfig | None:
        """
        Get the first enabled provider as default

        Returns:
            Default provider configuration or None
        """
        enabled = self.list_enabled_providers()
        return enabled[0] if enabled else None

    def create_sdk_instance(self, provider_id: str):
        """
        Create an SDK instance for a provider

        Args:
            provider_id: Provider ID

        Returns:
            SDK instance or None
        """
        config = self.get_provider(provider_id)
        if not config or not config.enabled:
            return None

        try:
            if config.sdk_mode == SdkMode.ANTHROPIC:
                from core.llm_sdk.anthropic.sdk import AnthropicSDK
                return AnthropicSDK(
                    api_key=config.api_key,
                    base_url=config.base_url
                )
            elif config.sdk_mode == SdkMode.OPENAI:
                from core.llm_sdk.openai.sdk import OpenAISDK
                return OpenAISDK(
                    api_key=config.api_key,
                    base_url=config.base_url
                )
        except Exception as e:
            print(f"Error creating SDK instance for {provider_id}: {e}")
            return None
