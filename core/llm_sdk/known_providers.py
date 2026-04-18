"""Known providers data structure - add providers here to auto-register"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SdkMode(Enum):
    """SDK mode for different API styles"""
    STANDARD = "standard"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OAI_RESPONSE = "oai-response"


class ProviderCategory(Enum):
    """Provider categories"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CUSTOM = "custom"


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a provider"""
    requests_per_second: int = 1
    window_ms: int = 1000


@dataclass
class RateLimitSelection:
    """Rate limit selection with SDK-specific overrides"""
    default: RateLimitConfig | None = None
    openai: RateLimitConfig | None = None
    anthropic: RateLimitConfig | None = None
    responses: RateLimitConfig | None = None


@dataclass
class KnownProviderConfig:
    """Configuration for a known provider"""
    # Basic info
    id: str
    display_name: str
    category: ProviderCategory

    # SDK configuration
    sdk_mode: SdkMode = SdkMode.STANDARD
    base_url: str | None = None

    # Per-SDK configuration (use nested dicts like {"base_url": "..."})
    openai: dict[str, Any] | None = None
    anthropic: dict[str, Any] | None = None
    responses: dict[str, Any] | None = None

    # Model configuration
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    fetch_models: bool = False
    models_endpoint: str | None = None

    # API configuration
    api_key_env_var: str = ""
    api_key_template: str | None = None
    supports_api_key: bool | None = None

    # Headers and other provider-specific options
    custom_header: dict[str, Any] = field(default_factory=dict)

    # Rate limiting
    rate_limit: RateLimitSelection | None = None

    # Token limits (overrides context_length_manager defaults)
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    total_context_tokens: int | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)


# Known providers data structure
# Add new providers here to auto-register them in the system
KnownProviders: dict[str, KnownProviderConfig] = {
    "anthropic": KnownProviderConfig(
        id="anthropic",
        display_name="Anthropic Claude",
        category=ProviderCategory.ANTHROPIC,
        sdk_mode=SdkMode.ANTHROPIC,
        default_model="claude-3-5-sonnet-20241022",
        models=[
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        fetch_models=False,
        api_key_env_var="ANTHROPIC_API_KEY",
        rate_limit=RateLimitSelection(
            anthropic=RateLimitConfig(requests_per_second=1, window_ms=1000)
        ),
    ),

    "openai": KnownProviderConfig(
        id="openai",
        display_name="OpenAI GPT",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        default_model="gpt-4o",
        models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
        fetch_models=False,
        api_key_env_var="OPENAI_API_KEY",
        rate_limit=RateLimitSelection(
            openai=RateLimitConfig(requests_per_second=1, window_ms=1000)
        ),
    ),

    "copilot": KnownProviderConfig(
        id="copilot",
        display_name="GitHub Copilot",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.STANDARD,
        default_model="gpt-5",
        models=[
            "gpt-5",
            "claude-sonnet-4.5",
            "gpt-4.1",
        ],
        fetch_models=True,
        api_key_env_var="",
        metadata={
            "auth_mode": "logged_in_user",
            "provider_kind": "copilot",
        },
    ),

    # Providers imported from knownProvidersData.js (per-SDK nested dicts)
    "aihubmix": KnownProviderConfig(
        id="aihubmix",
        display_name="AIHubMix",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://aihubmix.com/v1",
        openai={"base_url": "https://aihubmix.com/v1"},
        anthropic={"base_url": "https://aihubmix.com"},
        custom_header={"APP-Code": "TFUV4759"},
        fetch_models=True,
        models_endpoint="/models",
        metadata={"family": "AIHubMix", "open_model_endpoint": True},
    ),

    "apertis": KnownProviderConfig(
        id="apertis",
        display_name="Apertis AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.apertis.ai/v1",
        openai={"base_url": "https://api.apertis.ai/v1"},
        anthropic={"base_url": "https://api.apertis.ai"},
        responses={"base_url": "https://api.apertis.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "blackbox": KnownProviderConfig(
        id="blackbox",
        display_name="Blackbox AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.blackbox.ai/v1",
        openai={"base_url": "https://api.blackbox.ai/v1"},
        anthropic={"base_url": "https://api.blackbox.ai/"},
        responses={"base_url": "https://api.blackbox.ai/v1"},
        custom_header={"anthropic-version": "2023-06-01"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="YOUR_BLACKBOX_API_KEY",
    ),

    "cortecs": KnownProviderConfig(
        id="cortecs",
        display_name="Cortecs",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.cortecs.ai/v1",
        openai={"base_url": "https://api.cortecs.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "chatjimmy": KnownProviderConfig(
        id="chatjimmy",
        display_name="ChatJimmy",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.STANDARD,
    ),

    "ava-supernova": KnownProviderConfig(
        id="ava-supernova",
        display_name="AVA Supernova",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://ava-supernova.com/api/v1",
        openai={"base_url": "https://ava-supernova.com/api/v1"},
        fetch_models=False,
    ),

    "cline": KnownProviderConfig(
        id="cline",
        display_name="Cline",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.cline.bot/api/v1",
        openai={"base_url": "https://api.cline.bot/api/v1"},
        fetch_models=True,
        models_endpoint="https://api.cline.bot/api/v1/ai/cline/models",
    ),

    "chutes": KnownProviderConfig(
        id="chutes",
        display_name="Chutes AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://llm.chutes.ai/v1",
        openai={"base_url": "https://llm.chutes.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "codex": KnownProviderConfig(
        id="codex",
        display_name="OpenAI Codex",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
    ),

    "dinference": KnownProviderConfig(
        id="dinference",
        display_name="Dinference",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.dinference.com/v1",
        openai={"base_url": "https://api.dinference.com/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "fireworks": KnownProviderConfig(
        id="fireworks",
        display_name="Fireworks AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.fireworks.ai/inference/v1",
        openai={"base_url": "https://api.fireworks.ai/inference/v1"},
        anthropic={"base_url": "https://api.fireworks.ai/inference/v1"},
        responses={"base_url": "https://api.fireworks.ai/inference/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "fastrouter": KnownProviderConfig(
        id="fastrouter",
        display_name="FastRouter",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.ANTHROPIC,
        base_url="https://api.fastrouter.ai/api/v1",
        openai={"base_url": "https://api.fastrouter.ai/api/v1"},
        anthropic={"base_url": "https://api.fastrouter.ai/api/v1"},
        responses={"base_url": "https://api.fastrouter.ai/api/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "friendli": KnownProviderConfig(
        id="friendli",
        display_name="Friendli",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.friendli.ai/serverless/v1",
        openai={"base_url": "https://api.friendli.ai/serverless/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "compatible": KnownProviderConfig(
        id="compatible",
        display_name="OpenAI/Anthropic Compatible",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.STANDARD,
        metadata={"settings_prefix": "aether.compatibleModels"},
    ),

    "deepinfra": KnownProviderConfig(
        id="deepinfra",
        display_name="DeepInfra",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.deepinfra.com/v1/openai",
        openai={"base_url": "https://api.deepinfra.com/v1/openai"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "deepseek": KnownProviderConfig(
        id="deepseek",
        display_name="DeepSeek",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.deepseek.com/v1",
        openai={"base_url": "https://api.deepseek.com/v1"},
        anthropic={"base_url": "https://api.deepseek.com/anthropic"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "huggingface": KnownProviderConfig(
        id="huggingface",
        display_name="Hugging Face",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://router.huggingface.co/v1",
        openai={"base_url": "https://router.huggingface.co/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "jiekou": KnownProviderConfig(
        id="jiekou",
        display_name="Jiekou AI",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.jiekou.ai/openai/",
        openai={"base_url": "https://api.jiekou.ai/openai/"},
        anthropic={"base_url": "https://api.jiekou.ai/anthropic"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "meganova": KnownProviderConfig(
        id="meganova",
        display_name="MegaNova",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://inference.meganova.ai/v1",
        openai={"base_url": "https://inference.meganova.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "kilo": KnownProviderConfig(
        id="kilo",
        display_name="Kilo AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.kilo.ai/api/gateway",
        openai={"base_url": "https://api.kilo.ai/api/gateway"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "lightningai": KnownProviderConfig(
        id="lightningai",
        display_name="LightningAI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://lightning.ai/api/v1",
        openai={"base_url": "https://lightning.ai/api/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "dashscope": KnownProviderConfig(
        id="dashscope",
        display_name="DashScope (Ali Bailian)",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://coding.dashscope.aliyuncs.com/v1",
        openai={"base_url": "https://coding.dashscope.aliyuncs.com/v1"},
        anthropic={"base_url": "https://coding.dashscope.aliyuncs.com/apps/anthropic"},
        fetch_models=False,
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "minimax": KnownProviderConfig(
        id="minimax",
        display_name="MiniMax",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.minimaxi.com/v1",
        openai={"base_url": "https://api.minimaxi.com/v1"},
        anthropic={"base_url": "https://api.minimaxi.com/anthropic"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "mistral": KnownProviderConfig(
        id="mistral",
        display_name="Mistral AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.mistral.ai/v1",
        openai={"base_url": "https://api.mistral.ai/v1"},
        fetch_models=False,
        api_key_template="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "moark": KnownProviderConfig(
        id="moark",
        display_name="Moark",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.moark.ai/v1",
        openai={"base_url": "https://api.moark.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "modelscope": KnownProviderConfig(
        id="modelscope",
        display_name="ModelScope",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api-inference.modelscope.ai/v1",
        openai={"base_url": "https://api-inference.modelscope.ai/v1"},
        anthropic={"base_url": "https://api-inference.modelscope.ai"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "llmgateway": KnownProviderConfig(
        id="llmgateway",
        display_name="LLMGateway",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.llmgateway.io/v1",
        openai={"base_url": "https://api.llmgateway.io/v1"},
        anthropic={"base_url": "https://api.llmgateway.io"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "moonshot": KnownProviderConfig(
        id="moonshot",
        display_name="MoonshotAI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.moonshot.ai/v1",
        openai={"base_url": "https://api.moonshot.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "nanogpt": KnownProviderConfig(
        id="nanogpt",
        display_name="NanoGPT",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://nano-gpt.com/api/v1",
        openai={"base_url": "https://nano-gpt.com/api/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "modal": KnownProviderConfig(
        id="modal",
        display_name="Modal (Research)",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.us-west-2.modal.direct/v1",
        openai={"base_url": "https://api.us-west-2.modal.direct/v1"},
        fetch_models=False,
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "nvidia": KnownProviderConfig(
        id="nvidia",
        display_name="NVIDIA NIM",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://integrate.api.nvidia.com/v1",
        openai={"base_url": "https://integrate.api.nvidia.com/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "ollama": KnownProviderConfig(
        id="ollama",
        display_name="Ollama",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://ollama.com/v1",
        openai={"base_url": "https://ollama.com/v1"},
        anthropic={"base_url": "https://ollama.com"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "opencode": KnownProviderConfig(
        id="opencode",
        display_name="OpenCode",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://opencode.ai/zen/v1",
        openai={"base_url": "https://opencode.ai/zen/v1"},
        anthropic={"base_url": "https://opencode.ai/zen"},
        fetch_models=True,
        models_endpoint="/models",
        rate_limit=RateLimitSelection(
            default=RateLimitConfig(requests_per_second=1, window_ms=1000),
            openai=RateLimitConfig(requests_per_second=1, window_ms=1000),
            anthropic=RateLimitConfig(requests_per_second=1, window_ms=1000),
        ),
    ),

    "opencodego": KnownProviderConfig(
        id="opencodego",
        display_name="OpenCode Zen Go",
        category=ProviderCategory.CUSTOM,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://opencode.ai/zen/go/v1",
        openai={"base_url": "https://opencode.ai/zen/go/v1"},
        anthropic={"base_url": "https://opencode.ai/zen/go"},
        fetch_models=False,
    ),

    "pollinations": KnownProviderConfig(
        id="pollinations",
        display_name="Pollinations AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://gen.pollinations.ai/v1",
        openai={"base_url": "https://gen.pollinations.ai/v1"},
        fetch_models=False,
        api_key_template="sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ),

    "qwencli": KnownProviderConfig(
        id="qwencli",
        display_name="Qwen CLI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        openai={"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    ),

    "seraphyn": KnownProviderConfig(
        id="seraphyn",
        display_name="Seraphyn",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://seraphyn.ai/api/v1",
        openai={"base_url": "https://seraphyn.ai/api/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxx",
    ),

    "vercelai": KnownProviderConfig(
        id="vercelai",
        display_name="Vercel AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://ai-gateway.vercel.sh/v1",
        openai={"base_url": "https://ai-gateway.vercel.sh/v1"},
        fetch_models=True,
        models_endpoint="/models",
        metadata={
            "model_parser": {
                "arrayPath": "data",
                "filterField": "type",
                "filterValue": "language",
                "contextLengthField": "context_window",
                "tagsField": "tags",
                "descriptionField": "id",
                "cooldownMinutes": 10,
            }
        },
    ),

    "zenmux": KnownProviderConfig(
        id="zenmux",
        display_name="Zenmux",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://zenmux.ai/api/v1",
        openai={"base_url": "https://zenmux.ai/api/v1"},
        fetch_models=True,
        models_endpoint="/models",
    ),

    "knox": KnownProviderConfig(
        id="knox",
        display_name="Knox",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.knox.chat/v1",
        openai={"base_url": "https://api.knox.chat/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxx",
    ),

    "hicapai": KnownProviderConfig(
        id="hicapai",
        display_name="HicapAI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.hicap.ai/v1",
        openai={"base_url": "https://api.hicap.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        metadata={
            "model_parser": {
                "arrayPath": "data",
                "descriptionField": "id",
                "cooldownMinutes": 10,
            }
        },
    ),

    "baseten": KnownProviderConfig(
        id="baseten",
        display_name="Baseten",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://inference.baseten.co/v1",
        openai={"base_url": "https://inference.baseten.co/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="pt-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        metadata={"open_model_endpoint": False},
    ),

    "berget": KnownProviderConfig(
        id="berget",
        display_name="Berget",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.berget.ai/v1",
        openai={"base_url": "https://api.berget.ai/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        metadata={"open_model_endpoint": True},
    ),

    "sherlock": KnownProviderConfig(
        id="sherlock",
        display_name="Sherlock (CloudFerro)",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api-sherlock.cloudferro.com/openai/v1",
        openai={"base_url": "https://api-sherlock.cloudferro.com/openai/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        metadata={"open_model_endpoint": False},
    ),

    "clarifai": KnownProviderConfig(
        id="clarifai",
        display_name="Clarifai",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.clarifai.com/v2/ext/openai/v1",
        openai={"base_url": "https://api.clarifai.com/v2/ext/openai/v1"},
        responses={"base_url": "https://api.clarifai.com/v2/ext/openai/v1"},
        fetch_models=True,
        models_endpoint="/models",
        api_key_template="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        metadata={"open_model_endpoint": False},
    ),

    "zhipu": KnownProviderConfig(
        id="zhipu",
        display_name="Zhipu AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        openai={"base_url": "https://open.bigmodel.cn/api/paas/v4"},
    ),

    "puter": KnownProviderConfig(
        id="puter",
        display_name="Puter AI",
        category=ProviderCategory.OPENAI,
        sdk_mode=SdkMode.OPENAI,
        base_url="https://api.puter.com/puterai/openai/v1",
        openai={"base_url": "https://api.puter.com/puterai/openai/v1"},
        fetch_models=False,
        api_key_template="YOUR_PUTER_AUTH_TOKEN",
        metadata={"open_model_endpoint": False},
    ),
}


def get_known_provider(provider_id: str) -> KnownProviderConfig | None:
    """Get a known provider configuration by ID"""
    return KnownProviders.get(provider_id)


def list_known_providers() -> list[KnownProviderConfig]:
    """List all known providers"""
    return list(KnownProviders.values())


def get_known_providers_by_category(category: ProviderCategory) -> list[KnownProviderConfig]:
    """Get all providers in a specific category"""
    return [p for p in KnownProviders.values() if p.category == category]


def register_known_provider(config: KnownProviderConfig):
    """
    Register a new known provider programmatically

    Args:
        config: Provider configuration to register
    """
    KnownProviders[config.id] = config


def unregister_known_provider(provider_id: str):
    """
    Unregister a known provider

    Args:
        provider_id: Provider ID to unregister
    """
    if provider_id in KnownProviders:
        del KnownProviders[provider_id]


def load_static_models(provider_id: str) -> dict[str, Any] | None:
    """
    Load static models from a JSON file for a provider

    Args:
        provider_id: Provider ID to load models for

    Returns:
        Dictionary with models data or None if file not found
    """
    # Try to load from provider/models/<provider_id>.json
    current_dir = os.path.dirname(__file__)
    models_file_path = os.path.join(current_dir, "provider", "models", f"{provider_id}.json")

    if not os.path.exists(models_file_path):
        return None

    try:
        with open(models_file_path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Failed to load static models for {provider_id}: {e}")
        return None


def get_provider_models(provider_id: str) -> list[str]:
    """
    Get models for a provider, using static models file if available

    Args:
        provider_id: Provider ID

    Returns:
        List of model IDs
    """
    # Try static models file first
    static_data = load_static_models(provider_id)
    if static_data and "models" in static_data:
        # Handle aether-style format with models array
        return [model["id"] for model in static_data["models"]]

    # Fall back to provider config models
    provider = get_known_provider(provider_id)
    if provider:
        return provider.models

    return []


def get_provider_model_config(provider_id: str) -> dict[str, Any] | None:
    """
    Get full model configuration for a provider from static file

    Args:
        provider_id: Provider ID

    Returns:
        Full config dictionary or None
    """
    return load_static_models(provider_id)


async def fetch_provider_models(provider_id: str, api_key: str | None = None) -> list[dict[str, Any]] | None:
    """
    Fetch models for a provider with caching and fallback

    Args:
        provider_id: Provider ID
        api_key: Optional API key for authenticated requests

    Returns:
        List of model configs or None
    """
    from .model_fetcher import model_fetcher
    return await model_fetcher.fetch_models(provider_id, api_key)


def fetch_provider_models_background(provider_id: str, api_key: str | None = None):
    """
    Fetch models for a provider in background

    Args:
        provider_id: Provider ID
        api_key: Optional API key
    """
    import asyncio

    from .model_fetcher import model_fetcher
    asyncio.create_task(model_fetcher.fetch_background(provider_id, api_key))
