"""Context length manager for managing token limits across different models"""

from dataclasses import dataclass
from enum import Enum


class ModelFamily(Enum):
    """Model families for context length configuration"""
    CLAUDE = "claude"
    GPT = "gpt"
    DEFAULT = "default"
    ZHIPU = "zhipu"
    DEEPSEEK = "deepseek"
    MINIMAX = "minimax"
    GEMMA = "gemma"
    QWEN = "qwen"
    NEMOTRON = "nemotron"
    GEMINI = "gemini"


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

    # Default values
    DEFAULT_CONTEXT_LENGTH = 128 * TOKENS_PER_KIBI  # 131072
    DEFAULT_MAX_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384
    DEFAULT_MIN_RESERVED_INPUT_TOKENS = 1024

    # Claude models: 200K total context, 32K output / 168K input
    CLAUDE_TOTAL_TOKENS = 200 * TOKENS_PER_KIBI  # 204800
    CLAUDE_MAX_INPUT_TOKENS = CLAUDE_TOTAL_TOKENS - 32 * TOKENS_PER_KIBI  # 172032
    CLAUDE_MAX_OUTPUT_TOKENS = 32 * TOKENS_PER_KIBI  # 32768

    # GPT-4 models: 128K total context, 16K output / 112K input
    GPT4_TOTAL_TOKENS = 128 * TOKENS_PER_KIBI  # 131072
    GPT4_MAX_INPUT_TOKENS = GPT4_TOTAL_TOKENS - 16 * TOKENS_PER_KIBI  # 114688
    GPT4_MAX_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384

    # GPT-4o models: 128K total context, 16K output / 112K input
    GPT4O_TOTAL_TOKENS = 128 * TOKENS_PER_KIBI  # 131072
    GPT4O_MAX_INPUT_TOKENS = GPT4O_TOTAL_TOKENS - 16 * TOKENS_PER_KIBI  # 114688
    GPT4O_MAX_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384

    # DeepSeek models: 160K total context, 16K output / 144K input
    DEEPSEEK_TOTAL_TOKENS = 160 * TOKENS_PER_KIBI  # 163840
    DEEPSEEK_MAX_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384
    DEEPSEEK_MAX_INPUT_TOKENS = DEEPSEEK_TOTAL_TOKENS - DEEPSEEK_MAX_OUTPUT_TOKENS  # 147456

    # Fixed 128K family: 16K output / 112K input
    FIXED_128K_MAX_INPUT_TOKENS = 128 * TOKENS_PER_KIBI - 16 * TOKENS_PER_KIBI  # 114688
    FIXED_128K_MAX_OUTPUT_TOKENS = 16 * TOKENS_PER_KIBI  # 16384

    # Fixed 256K family: 32K output / 224K input
    FIXED_256K_MAX_INPUT_TOKENS = 256 * TOKENS_PER_KIBI - 32 * TOKENS_PER_KIBI  # 229376
    FIXED_256K_MAX_OUTPUT_TOKENS = 32 * TOKENS_PER_KIBI  # 32768

    # Qwen 3.5 models: 256K total context, 32K output / 224K input
    QWEN35_MAX_INPUT_TOKENS = 256 * TOKENS_PER_KIBI - 32 * TOKENS_PER_KIBI  # 229376
    QWEN35_MAX_OUTPUT_TOKENS = 32 * TOKENS_PER_KIBI  # 32768

    # Qwen 3.5 Flash / Plus models: 1M total context, 32K output
    QWEN35_1M_TOTAL_TOKENS = TOKENS_PER_MEBI
    QWEN35_1M_MAX_OUTPUT_TOKENS = 32 * TOKENS_PER_KIBI  # 32768
    QWEN35_1M_MAX_INPUT_TOKENS = QWEN35_1M_TOTAL_TOKENS - QWEN35_1M_MAX_OUTPUT_TOKENS

    def __init__(self):
        self._model_limits: dict[str, TokenLimits] = {}
        self._initialize_default_limits()

    def _initialize_default_limits(self):
        """Initialize default token limits for common models"""
        # Claude models
        self._model_limits.update({
            "claude-3-opus-20240229": TokenLimits(
                max_input_tokens=self.CLAUDE_MAX_INPUT_TOKENS,
                max_output_tokens=self.CLAUDE_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.CLAUDE_TOTAL_TOKENS
            ),
            "claude-3-sonnet-20240229": TokenLimits(
                max_input_tokens=self.CLAUDE_MAX_INPUT_TOKENS,
                max_output_tokens=self.CLAUDE_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.CLAUDE_TOTAL_TOKENS
            ),
            "claude-3-haiku-20240307": TokenLimits(
                max_input_tokens=self.CLAUDE_MAX_INPUT_TOKENS,
                max_output_tokens=self.CLAUDE_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.CLAUDE_TOTAL_TOKENS
            ),
            "claude-3-5-sonnet-20241022": TokenLimits(
                max_input_tokens=self.CLAUDE_MAX_INPUT_TOKENS,
                max_output_tokens=self.CLAUDE_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.CLAUDE_TOTAL_TOKENS
            ),
            "claude-3-5-haiku-20241022": TokenLimits(
                max_input_tokens=self.CLAUDE_MAX_INPUT_TOKENS,
                max_output_tokens=self.CLAUDE_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.CLAUDE_TOTAL_TOKENS
            ),
        })

        # GPT models
        self._model_limits.update({
            "gpt-4": TokenLimits(
                max_input_tokens=self.GPT4_MAX_INPUT_TOKENS,
                max_output_tokens=self.GPT4_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.GPT4_TOTAL_TOKENS
            ),
            "gpt-4-turbo": TokenLimits(
                max_input_tokens=self.GPT4_MAX_INPUT_TOKENS,
                max_output_tokens=self.GPT4_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.GPT4_TOTAL_TOKENS
            ),
            "gpt-4o": TokenLimits(
                max_input_tokens=self.GPT4O_MAX_INPUT_TOKENS,
                max_output_tokens=self.GPT4O_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.GPT4O_TOTAL_TOKENS
            ),
            "gpt-4o-mini": TokenLimits(
                max_input_tokens=self.FIXED_128K_MAX_INPUT_TOKENS,
                max_output_tokens=self.FIXED_128K_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.DEFAULT_CONTEXT_LENGTH
            ),
            "gpt-3.5-turbo": TokenLimits(
                max_input_tokens=self.FIXED_128K_MAX_INPUT_TOKENS,
                max_output_tokens=self.FIXED_128K_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.DEFAULT_CONTEXT_LENGTH
            ),
        })

        # DeepSeek models
        self._model_limits.update({
            "deepseek-chat": TokenLimits(
                max_input_tokens=self.DEEPSEEK_MAX_INPUT_TOKENS,
                max_output_tokens=self.DEEPSEEK_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.DEEPSEEK_TOTAL_TOKENS
            ),
            "deepseek-coder": TokenLimits(
                max_input_tokens=self.DEEPSEEK_MAX_INPUT_TOKENS,
                max_output_tokens=self.DEEPSEEK_MAX_OUTPUT_TOKENS,
                total_context_tokens=self.DEEPSEEK_TOTAL_TOKENS
            ),
        })

    def get_token_limits(self, model: str) -> TokenLimits:
        """
        Get token limits for a specific model

        Args:
            model: Model name

        Returns:
            TokenLimits for the model
        """
        if model in self._model_limits:
            return self._model_limits[model]

        # Try to match by prefix
        for model_name, limits in self._model_limits.items():
            if model.startswith(model_name.split('-')[0]):
                return limits

        # Return default limits
        return TokenLimits(
            max_input_tokens=self.DEFAULT_CONTEXT_LENGTH - self.DEFAULT_MAX_OUTPUT_TOKENS,
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
        limits = self.get_token_limits(model)

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
