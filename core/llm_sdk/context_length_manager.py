"""Context length manager for managing token limits across different models"""

import json
import logging
import os
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger(__name__)


class ModelFamily(Enum):
    """Model families for context length configuration"""
    DEFAULT = "default"


@dataclass
class TokenLimits:
    """Token limits for a model"""
    total_context_tokens: int
    max_output_tokens: int = 4096


class ContextLengthManager:
    """Manages context length and token limits for different models"""

    # Token constants
    TOKENS_PER_KIBI = 1024
    TOKENS_PER_MEBI = TOKENS_PER_KIBI * TOKENS_PER_KIBI

    # Default values (configurable via .env)
    DEFAULT_CONTEXT_LENGTH = 128 * TOKENS_PER_KIBI  # 131072
    DEFAULT_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384

    # API URL for model limits
    MODELS_DEV_API_URL = "https://models.dev/api.json"

    def __init__(self):
        self._model_limits: dict[str, TokenLimits] = {}
        self._loaded = False

    def load_model_limits(self) -> None:
        """Load model limits from models.dev API"""
        if self._loaded:
            return

        # Run in background thread to not block the async event loop
        def _fetch_in_background() -> None:
            try:
                request = Request(self.MODELS_DEV_API_URL, headers={"User-Agent": "JARVIS/1.0"})
                with urlopen(request, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    self._parse_model_limits(data)
                    logger.info(f"Loaded model limits from {self.MODELS_DEV_API_URL}")
            except URLError as e:
                logger.warning(f"Failed to fetch model limits: {e}")
            except Exception as e:
                logger.warning(f"Failed to load model limits: {e}")
            finally:
                self._loaded = True

        # Start background thread
        thread = threading.Thread(target=_fetch_in_background, daemon=True)
        thread.start()

    def _parse_model_limits(self, data: dict[str, Any]) -> None:
        """Parse model limits from API response"""
        # The API has providers as keys, each with models
        for provider_name, provider_data in data.items():
            if not isinstance(provider_data, dict):
                continue

            models = provider_data.get("models", {})
            if not models:
                continue

            for model_id, model_info in models.items():
                limit = model_info.get("limit", {})
                if not limit:
                    continue

                context_tokens = limit.get("context", 0)
                output_tokens = limit.get("output", self.DEFAULT_OUTPUT_TOKENS)

                if context_tokens > 0:
                    # Store using the model ID (can be accessed as-is or normalized)
                    self._model_limits[model_id] = TokenLimits(
                        total_context_tokens=context_tokens,
                        max_output_tokens=output_tokens
                    )

    def get_token_limits(self, model: str) -> TokenLimits:
        """
        Get token limits for a specific model

        Args:
            model: Model name

        Returns:
            TokenLimits with values from API or defaults
        """
        # Check if we have specific limits for this model
        if model in self._model_limits:
            return self._model_limits[model]

        # Try to find a match by partial name (e.g., "gpt-4" matches "gpt-4o")
        for model_id, limits in self._model_limits.items():
            if model.lower() in model_id.lower() or model_id.lower() in model.lower():
                return limits

        # Return default limits
        return TokenLimits(
            total_context_tokens=self.DEFAULT_CONTEXT_LENGTH,
            max_output_tokens=self.DEFAULT_OUTPUT_TOKENS
        )

    def register_model_limits(
        self,
        model: str,
        total_context_tokens: int,
        max_output_tokens: int | None = None
    ):
        """
        Register custom token limits for a model

        Args:
            model: Model name
            total_context_tokens: Total context tokens
            max_output_tokens: Max output tokens (optional)
        """
        self._model_limits[model] = TokenLimits(
            total_context_tokens=total_context_tokens,
            max_output_tokens=max_output_tokens or self.DEFAULT_OUTPUT_TOKENS
        )

    def resolve_token_limits(
        self,
        model: str,
        default_context_length: int | None = None,
    ) -> TokenLimits:
        """
        Resolve token limits with fallbacks

        Args:
            model: Model name
            default_context_length: Default context length if model not found

        Returns:
            Resolved TokenLimits
        """
        limits = self.get_token_limits(model)

        # Apply defaults if provided
        if default_context_length:
            limits.total_context_tokens = default_context_length

        return limits

    def get_total_context_tokens(self, model: str) -> int:
        """Get total context tokens for a model"""
        return self.get_token_limits(model).total_context_tokens

    def get_max_output_tokens(self, model: str) -> int:
        """Get max output tokens for a model"""
        return self.get_token_limits(model).max_output_tokens


# Global instance
context_length_manager = ContextLengthManager()