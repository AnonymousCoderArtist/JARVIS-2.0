"""Background model fetching for providers"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from .known_providers import get_known_provider, load_static_models


class ModelCache:
    """Cache for fetched provider models"""

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), ".model_cache")
        self.cache_duration = timedelta(hours=6)  # Cache for 6 hours
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, provider_id: str) -> str:
        return os.path.join(self.cache_dir, f"{provider_id}.json")

    def get(self, provider_id: str) -> dict[str, Any] | None:
        """Get cached models for a provider"""
        cache_path = self._get_cache_path(provider_id)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check if cache is expired
            cached_at = datetime.fromisoformat(cache_data.get("cached_at", ""))
            if datetime.now() - cached_at > self.cache_duration:
                return None

            return cache_data.get("data")
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def set(self, provider_id: str, data: dict[str, Any]):
        """Cache models for a provider"""
        cache_path = self._get_cache_path(provider_id)
        cache_data = {
            "cached_at": datetime.now().isoformat(),
            "data": data
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except OSError as e:
            print(f"Failed to cache models for {provider_id}: {e}")

    def invalidate(self, provider_id: str):
        """Invalidate cache for a provider"""
        cache_path = self._get_cache_path(provider_id)
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except OSError:
                pass


class ModelFetcher:
    """Background model fetcher for providers"""

    def __init__(self):
        self.cache = ModelCache()
        self._fetch_tasks: dict[str, asyncio.Task] = {}

    async def fetch_models(
        self,
        provider_id: str,
        api_key: str | None = None
    ) -> list[dict[str, Any]] | None:
        """
        Fetch models for a provider, using cache and fallback

        Args:
            provider_id: Provider ID
            api_key: Optional API key for authenticated requests

        Returns:
            List of model configs or None
        """
        provider = get_known_provider(provider_id)
        if not provider:
            return None

        # Try cache first
        cached = self.cache.get(provider_id)
        if cached and cached.get("models"):
            return cached["models"]

        # Try static models file
        static_data = load_static_models(provider_id)
        if static_data and static_data.get("models"):
            return static_data["models"]

        # If provider supports dynamic fetching, try that
        if provider.fetch_models and provider.models_endpoint:
            try:
                models = await self._fetch_from_api(provider, api_key)
                if models:
                    # Cache the result
                    self.cache.set(provider_id, {"models": models})
                    return models
            except Exception as e:
                print(f"Failed to fetch models for {provider_id} from API: {e}")

        return None

    async def _fetch_from_api(
        self,
        provider,
        api_key: str | None = None
    ) -> list[dict[str, Any]] | None:
        """Fetch models from provider API"""
        if not provider.base_url:
            return None

        # Build full URL
        endpoint = provider.models_endpoint.lstrip('/')
        url = f"{provider.base_url.rstrip('/')}/{endpoint}"

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Add custom headers if present
        if provider.custom_header:
            headers.update(provider.custom_header)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Parse models based on common response formats
            if isinstance(data, dict):
                # Try common array paths
                models = data.get("data", data.get("models", []))
            elif isinstance(data, list):
                models = data
            else:
                return None

            # Normalize model data to aether-style format
            normalized = []
            for model in models:
                if isinstance(model, dict):
                    normalized.append({
                        "id": model.get("id", model.get("name", "")),
                        "name": model.get("name", model.get("id", "")),
                        "tooltip": model.get("description", ""),
                        "maxInputTokens": model.get("max_input_tokens", model.get("context_length", 0)),
                        "maxOutputTokens": model.get("max_output_tokens", 0),
                        "sdkMode": provider.sdk_mode.value if provider.sdk_mode else "openai",
                        "baseUrl": provider.base_url,
                        "capabilities": {
                            "toolCalling": model.get("supports_tools", True),
                            "imageInput": model.get("supports_images", False)
                        }
                    })

            return normalized

    async def fetch_background(self, provider_id: str, api_key: str | None = None):
        """
        Fetch models in background without blocking

        Args:
            provider_id: Provider ID
            api_key: Optional API key
        """
        if provider_id in self._fetch_tasks:
            # Already fetching
            return

        async def _fetch():
            try:
                await self.fetch_models(provider_id, api_key)
            finally:
                self._fetch_tasks.pop(provider_id, None)

        self._fetch_tasks[provider_id] = asyncio.create_task(_fetch())

    def get_model_ids(self, provider_id: str, api_key: str | None = None) -> list[str]:
        """
        Get model IDs for a provider (synchronous wrapper)

        Args:
            provider_id: Provider ID
            api_key: Optional API key

        Returns:
            List of model IDs
        """
        # Try cache first
        cached = self.cache.get(provider_id)
        if cached and cached.get("models"):
            return [m["id"] for m in cached["models"]]

        # Try static models
        static_data = load_static_models(provider_id)
        if static_data and static_data.get("models"):
            return [m["id"] for m in static_data["models"]]

        # Fall back to provider config
        provider = get_known_provider(provider_id)
        if provider:
            return provider.models

        return []


# Global model fetcher instance
model_fetcher = ModelFetcher()
