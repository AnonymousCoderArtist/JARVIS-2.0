"""Model information fetching and caching from models.dev API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any
import httpx

API_URL = "https://models.dev/api.json"
_cache: dict[str, Any] = {}
_cache_time: datetime | None = None
_cache_ttl = 3600  # 1 hour
_fuzzy_threshold = 0.7  # Minimum similarity ratio for fuzzy matching


@dataclass
class ModelLimit:
    """Model context/output limits."""
    context: int
    output: int


@dataclass
class ModelCost:
    """Model pricing per 1M tokens."""
    input: float
    output: float


@dataclass
class ModelCapabilities:
    """Model capabilities and features."""
    reasoning: bool = False
    tool_call: bool = False
    temperature: bool = False
    structured_output: bool = False
    vision: bool = False
    audio_input: bool = False
    audio_output: bool = False


@dataclass
class ModelModalities:
    """Input/output modalities supported by model."""
    input: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)


@dataclass
class ModelInfo:
    """Complete model information."""
    id: str
    name: str
    provider_id: str
    provider_name: str
    family: str | None = None
    reasoning: bool = False
    tool_call: bool = False
    temperature: bool = False
    structured_output: bool = False
    knowledge_date: str | None = None
    release_date: str | None = None
    last_updated: str | None = None
    modalities: ModelModalities = field(default_factory=ModelModalities)
    limit: ModelLimit | None = None
    cost: ModelCost | None = None
    open_weights: bool = False
    attachment: bool = False


async def fetch_model_info() -> dict[str, ModelInfo]:
    """Fetch model information from models.dev API."""
    global _cache, _cache_time

    now = datetime.now()
    if _cache and _cache_time:
        age = (now - _cache_time).total_seconds()
        if age < _cache_ttl:
            return _cache

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(API_URL)
            response.raise_for_status()
            data = response.json()
    except Exception:
        # Return cached data if available, even if stale
        return _cache if _cache else {}

    _cache = _parse_model_data(data)
    _cache_time = now
    return _cache


def _parse_model_data(data: dict[str, Any]) -> dict[str, ModelInfo]:
    """Parse raw API data into ModelInfo objects."""
    models: dict[str, ModelInfo] = {}

    for provider_id, provider_data in data.items():
        provider_name = provider_data.get("name", provider_id)

        for model_id, model_data in provider_data.get("models", {}).items():
            capabilities = ModelCapabilities(
                reasoning=model_data.get("reasoning", False),
                tool_call=model_data.get("tool_call", False),
                temperature=model_data.get("temperature", False),
                structured_output=model_data.get("structured_output", False),
                vision="image" in model_data.get("modalities", {}).get("input", []),
                audio_input="audio" in model_data.get("modalities", {}).get("input", []),
                audio_output="audio" in model_data.get("modalities", {}).get("output", []),
            )

            modalities_data = model_data.get("modalities", {})
            modalities = ModelModalities(
                input=modalities_data.get("input", []),
                output=modalities_data.get("output", []),
            )

            limit_data = model_data.get("limit", {})
            limit = ModelLimit(
                context=limit_data.get("context", 0),
                output=limit_data.get("output", 0),
            ) if limit_data else None

            cost_data = model_data.get("cost", {})
            cost = ModelCost(
                input=cost_data.get("input", 0.0),
                output=cost_data.get("output", 0.0),
            ) if cost_data else None

            models[model_id] = ModelInfo(
                id=model_id,
                name=model_data.get("name", model_id),
                provider_id=provider_id,
                provider_name=provider_name,
                family=model_data.get("family"),
                reasoning=capabilities.reasoning,
                tool_call=capabilities.tool_call,
                temperature=capabilities.temperature,
                structured_output=capabilities.structured_output,
                knowledge_date=model_data.get("knowledge"),
                release_date=model_data.get("release_date"),
                last_updated=model_data.get("last_updated"),
                modalities=modalities,
                limit=limit,
                cost=cost,
                open_weights=model_data.get("open_weights", False),
                attachment=model_data.get("attachment", False),
            )

    return models


def _fuzzy_match(model_id: str, models: dict[str, ModelInfo]) -> ModelInfo | None:
    """Find the best matching model using fuzzy string matching.

    Args:
        model_id: The model identifier to match.
        models: Dictionary of available models.

    Returns:
        The best matching ModelInfo, or None if no match found.
    """
    # First try exact match
    if model_id in models:
        return models[model_id]

    # Try fuzzy matching
    best_match: ModelInfo | None = None
    best_ratio: float = 0.0

    model_lower = model_id.lower()

    for candidate_id, candidate_info in models.items():
        candidate_lower = candidate_id.lower()
        candidate_name = candidate_info.name.lower()

        # Try matching against model ID
        ratio = SequenceMatcher(None, model_lower, candidate_lower).ratio()
        if ratio > best_ratio and ratio >= _fuzzy_threshold:
            best_ratio = ratio
            best_match = candidate_info

        # Also try matching against model name
        ratio = SequenceMatcher(None, model_lower, candidate_name).ratio()
        if ratio > best_ratio and ratio >= _fuzzy_threshold:
            best_ratio = ratio
            best_match = candidate_info

    return best_match


async def get_model_info(model_id: str) -> ModelInfo | None:
    """Get information for a specific model with fuzzy matching fallback."""
    models = await fetch_model_info()
    return _fuzzy_match(model_id, models)


def get_model_context_window(model_id: str, default: int = 4096) -> int:
    """Get the context window size for a model with fuzzy matching."""
    info = asyncio.run(get_model_info(model_id))
    if info and info.limit:
        return info.limit.context
    return default


def get_model_output_limit(model_id: str, default: int = 4096) -> int:
    """Get the output token limit for a model with fuzzy matching."""
    info = asyncio.run(get_model_info(model_id))
    if info and info.limit:
        return info.limit.output
    return default


def get_model_info_sync(model_id: str) -> ModelInfo | None:
    """Get model info synchronously with fuzzy matching."""
    return asyncio.run(get_model_info(model_id))


def sync_fetch_model_info() -> dict[str, ModelInfo]:
    """Synchronously fetch model information."""
    try:
        return asyncio.run(fetch_model_info())
    except RuntimeError:
        # Already in async context
        return _cache if _cache else {}


def get_model_capabilities(model_id: str) -> ModelCapabilities:
    """Get capabilities for a model synchronously."""
    info = asyncio.run(get_model_info(model_id))
    if not info:
        return ModelCapabilities()
    return ModelCapabilities(
        reasoning=info.reasoning,
        tool_call=info.tool_call,
        temperature=info.temperature,
        structured_output=info.structured_output,
        vision="image" in info.modalities.input,
        audio_input="audio" in info.modalities.input,
        audio_output="audio" in info.modalities.output,
    )
if __name__ == "__main__":
    # Example usage
    import pprint

    model_info = get_model_capabilities("gpt-4o")
    pprint.pprint(model_info)