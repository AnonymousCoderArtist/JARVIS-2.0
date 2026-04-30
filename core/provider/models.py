"""Dynamic provider models for user-configurable LLM providers"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SdkMode(StrEnum):
    """SDK mode for different API styles"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    STANDARD = "standard"


@dataclass
class ProviderConfig:
    """Dynamic provider configuration"""
    provider_id: str
    api_key: str
    base_url: str | None = None
    sdk_mode: SdkMode = SdkMode.STANDARD
    enabled: bool = True
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "provider_id": self.provider_id,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "sdk_mode": self.sdk_mode.value,
            "enabled": self.enabled,
            "default_model": self.default_model,
            "models": self.models,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderConfig:
        """Create from dictionary"""
        return cls(
            provider_id=data["provider_id"],
            api_key=data["api_key"],
            base_url=data.get("base_url"),
            sdk_mode=SdkMode(data.get("sdk_mode", "standard")),
            enabled=data.get("enabled", True),
            default_model=data.get("default_model", ""),
            models=data.get("models", []),
            metadata=data.get("metadata", {}),
        )
