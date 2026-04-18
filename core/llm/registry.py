"""LLM Provider Registry for managing multiple providers"""

from typing import Dict, Optional, Type
import importlib.util
import sys
from pathlib import Path
from .base import BaseLLMProvider


class LLMProviderRegistry:
    """Registry for managing LLM providers"""

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._provider_classes: Dict[str, Type[BaseLLMProvider]] = {}

    def register(self, name: str, provider: BaseLLMProvider):
        """
        Register an LLM provider instance

        Args:
            name: Name to register the provider under
            provider: Provider instance
        """
        self._providers[name] = provider

    def register_class(self, name: str, provider_class: Type[BaseLLMProvider]):
        """
        Register an LLM provider class for later instantiation

        Args:
            name: Name to register the provider class under
            provider_class: Provider class
        """
        self._provider_classes[name] = provider_class

    def get(self, name: str) -> Optional[BaseLLMProvider]:
        """
        Get a registered provider by name

        Args:
            name: Provider name

        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(name)

    def instantiate(self, name: str, **kwargs) -> Optional[BaseLLMProvider]:
        """
        Instantiate a provider from a registered class

        Args:
            name: Provider class name
            **kwargs: Arguments to pass to provider constructor

        Returns:
            Provider instance or None if not found
        """
        provider_class = self._provider_classes.get(name)
        if provider_class:
            provider = provider_class(**kwargs)
            self.register(name, provider)
            return provider
        return None

    def list_providers(self) -> list[str]:
        """
        List all registered provider names

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    def register_plugin(self, plugin_path: str):
        """
        Dynamically load a provider plugin

        Args:
            plugin_path: Path to the plugin Python file
        """
        try:
            path = Path(plugin_path)
            if not path.exists():
                raise FileNotFoundError(f"Plugin file not found: {plugin_path}")

            spec = importlib.util.spec_from_file_location(
                f"plugin_{path.stem}", plugin_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Failed to load plugin: {plugin_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{path.stem}"] = module
            spec.loader.exec_module(module)

            # Look for a class that inherits from BaseLLMProvider
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseLLMProvider)
                    and attr != BaseLLMProvider
                ):
                    self.register_class(attr_name, attr)
                    print(f"Registered provider plugin: {attr_name}")
                    return

            raise ImportError(f"No valid provider class found in {plugin_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to load plugin {plugin_path}: {str(e)}")
