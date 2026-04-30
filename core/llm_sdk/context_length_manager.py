"""Context length manager for managing token limits across different models"""

import os
from dataclasses import dataclass
from enum import Enum


class ModelFamily(Enum):
    """Model families for context length configuration"""
    DEFAULT = "default"


@dataclass
class TokenLimits:
    """Token limits for a model"""
    max_input_tokens: int
    max_output_tokens: int
    total_context_tokens: int


class ContextLengthManager:
    """Manages context length and token limits for different models"""

    # Token constants
    TOKENS_PER_KIBI = 1024
    TOKENS_PER_MEBI = TOKENS_PER_KIBI * TOKENS_PER_KIBI

    # Default values (configurable via .env)
    # 128K total context (109K input + 16K output)
    DEFAULT_CONTEXT_LENGTH = 128 * TOKENS_PER_KIBI  # 131072
    DEFAULT_MAX_INPUT_TOKENS = 109 * TOKENS_PER_KIBI  # 111616
    DEFAULT_MAX_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384

    def __init__(self):
        self._model_limits: dict[str, TokenLimits] = {}
        self._load_env_config()
        self._initialize_default_limits()

    def _load_env_config(self):
        """Load custom token limits from environment variables"""
        # Load custom context length if specified
        env_context = os.getenv("JARVIS_MAX_CONTEXT_TOKENS")
        if env_context:
            try:
                self.DEFAULT_CONTEXT_LENGTH = int(env_context)
            except ValueError:
                pass

        # Load custom max input tokens if specified
        env_max_input = os.getenv("JARVIS_MAX_INPUT_TOKENS")
        if env_max_input:
            try:
                self.DEFAULT_MAX_INPUT_TOKENS = int(env_max_input)
            except ValueError:
                pass

        # Load custom max output tokens if specified
        env_max_output = os.getenv("JARVIS_MAX_OUTPUT_TOKENS")
        if env_max_output:
            try:
                self.DEFAULT_MAX_OUTPUT_TOKENS = int(env_max_output)
            except ValueError:
                pass

        # Recalculate to ensure consistency
        total = self.DEFAULT_MAX_INPUT_TOKENS + self.DEFAULT_MAX_OUTPUT_TOKENS
        if total > self.DEFAULT_CONTEXT_LENGTH:
            # Adjust input to fit within context
            self.DEFAULT_MAX_INPUT_TOKENS = self.DEFAULT_CONTEXT_LENGTH - self.DEFAULT_MAX_OUTPUT_TOKENS

    def _initialize_default_limits(self):
        """Initialize default token limits - using uniform defaults for all models"""
        # All models use the same default limits (no model-specific limits)
        pass

    def get_token_limits(self, model: str) -> TokenLimits:
        """
        Get token limits for a specific model

        Args:
            model: Model name (ignored, using uniform defaults)

        Returns:
            TokenLimits with default values
        """
        return TokenLimits(
            max_input_tokens=self.DEFAULT_MAX_INPUT_TOKENS,
            max_output_tokens=self.DEFAULT_MAX_OUTPUT_TOKENS,
            total_context_tokens=self.DEFAULT_CONTEXT_LENGTH
        )

    def register_model_limits(
        self,
        model: str,
        max_input_tokens: int,
        max_output_tokens: int,
        total_context_tokens: int | None = None
    ):
        """
        Register custom token limits for a model

        Args:
            model: Model name
            max_input_tokens: Maximum input tokens
            max_output_tokens: Maximum output tokens
            total_context_tokens: Total context tokens (optional, defaults to input + output)
        """
        if total_context_tokens is None:
            total_context_tokens = max_input_tokens + max_output_tokens

        self._model_limits[model] = TokenLimits(
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            total_context_tokens=total_context_tokens
        )

    def resolve_token_limits(
        self,
        model: str,
        default_context_length: int | None = None,
        default_max_output_tokens: int | None = None,
        min_reserved_input_tokens: int | None = None
    ) -> TokenLimits:
        """
        Resolve token limits with fallbacks

        Args:
            model: Model name
            default_context_length: Default context length if model not found
            default_max_output_tokens: Default max output tokens if model not found
            min_reserved_input_tokens: Minimum reserved input tokens

        Returns:
            Resolved TokenLimits
        """
        # Check if custom limits are registered for this model
        if model in self._model_limits:
            limits = self._model_limits[model]
        else:
            # Use default limits
            limits = TokenLimits(
                max_input_tokens=self.DEFAULT_MAX_INPUT_TOKENS,
                max_output_tokens=self.DEFAULT_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.DEFAULT_CONTEXT_LENGTH
            )

        # Apply defaults if provided
        if default_context_length:
            limits.total_context_tokens = default_context_length
        if default_max_output_tokens:
            limits.max_output_tokens = default_max_output_tokens

        # Ensure input + output doesn't exceed total
        if limits.max_input_tokens + limits.max_output_tokens > limits.total_context_tokens:
            limits.max_input_tokens = limits.total_context_tokens - limits.max_output_tokens

        # Apply minimum reserved input tokens
        if min_reserved_input_tokens and limits.max_input_tokens < min_reserved_input_tokens:
            limits.max_input_tokens = min_reserved_input_tokens
            limits.max_output_tokens = limits.total_context_tokens - limits.max_input_tokens

        return limits

    def get_max_input_tokens(self, model: str) -> int:
        """Get maximum input tokens for a model"""
        return self.get_token_limits(model).max_input_tokens

    def get_max_output_tokens(self, model: str) -> int:
        """Get maximum output tokens for a model"""
        return self.get_token_limits(model).max_output_tokens

    def get_total_context_tokens(self, model: str) -> int:
        """Get total context tokens for a model"""
        return self.get_token_limits(model).total_context_tokens


# Global instance
context_length_manager = ContextLengthManager()
