"""Configuration settings using TOML config file"""

import importlib
import os
import sys
from pathlib import Path
from typing import Any

from core.config.models import JarvisSettings

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _load_env_config() -> dict[str, Any]:
    """Load configuration from environment variables."""
    env_config: dict[str, Any] = {}
    
    # Heartbeat settings from environment
    heartbeat_env = {}
    if os.getenv("JARVIS_HEARTBEAT_ENABLED"):
        heartbeat_env["enabled"] = os.getenv("JARVIS_HEARTBEAT_ENABLED", "true").lower() in ("true", "1", "yes")
    if os.getenv("JARVIS_HEARTBEAT_EVERY"):
        heartbeat_env["every"] = os.getenv("JARVIS_HEARTBEAT_EVERY")
    if os.getenv("JARVIS_HEARTBEAT_TARGET"):
        heartbeat_env["target"] = os.getenv("JARVIS_HEARTBEAT_TARGET")
    if os.getenv("JARVIS_HEARTBEAT_LIGHT_CONTEXT"):
        heartbeat_env["light_context"] = os.getenv("JARVIS_HEARTBEAT_LIGHT_CONTEXT", "false").lower() in ("true", "1", "yes")
    if os.getenv("JARVIS_HEARTBEAT_SKIP_WHEN_BUSY"):
        heartbeat_env["skip_when_busy"] = os.getenv("JARVIS_HEARTBEAT_SKIP_WHEN_BUSY", "false").lower() in ("true", "1", "yes")
    if os.getenv("JARVIS_HEARTBEAT_SHOW_OK"):
        heartbeat_env["show_ok"] = os.getenv("JARVIS_HEARTBEAT_SHOW_OK", "true").lower() in ("true", "1", "yes")
    
    if heartbeat_env:
        env_config["heartbeat"] = heartbeat_env
    
    return env_config


class Settings:
    """Application settings loaded from config.toml with environment variable overrides"""

    def __init__(self, config_path: Path | None = None, initial_config: dict[str, Any] | None = None):
        self.config_path: Path = config_path or Path("config.toml")
        
        # Load TOML config first
        toml_config: dict[str, Any] = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "rb") as f:
                    toml_config = tomllib.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
        
        # Override with environment config
        env_config = _load_env_config()
        
        # Merge: start with toml, then env, then initial_config
        merged_config = self._deep_merge(toml_config, env_config)
        if initial_config:
            merged_config = self._deep_merge(merged_config, initial_config)
        
        self._config: JarvisSettings = JarvisSettings(**(merged_config or {}))
    
    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Settings._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
        """Get a configuration value."""
        if key is None:
            return getattr(self._config, section, default)
        
        section_data = getattr(self._config, section, None)
        if isinstance(section_data, dict):
            return section_data.get(key, default)
        elif hasattr(section_data, key):
            return getattr(section_data, key, default)
        return default

    def get_section(self, section: str) -> dict[str, Any]:
        """Get an entire configuration section as dict"""
        data = getattr(self._config, section, None)
        if hasattr(data, "model_dump"):
            return data.model_dump()
        return data if isinstance(data, dict) else {}

    def set(self, section: str, key: str | None, value: Any = None):
        """Set a configuration value."""
        if key is None:
            setattr(self._config, section, value)
            return

        section_obj = getattr(self._config, section, None)
        if isinstance(section_obj, dict):
            section_obj[key] = value
        elif hasattr(section_obj, "__dict__"):
            setattr(section_obj, key, value)

    def save(self) -> None:
        """Save configuration to TOML file"""
        try:
            import tomli_w
            with open(self.config_path, "wb") as f:
                toml_writer = importlib.import_module("tomli_w")
                toml_writer.dump(self._config.model_dump(), f)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

    # Convenience properties
    @property
    def app_name(self) -> str:
        return self._config.app.name

    @property
    def app_version(self) -> str:
        return self._config.app.version

    @property
    def debug(self) -> bool:
        return self._config.app.debug

    @property
    def selected_provider_id(self) -> str | None:
        return self._config.provider.selected_provider_id

    @property
    def provider_config_file(self) -> str:
        return self._config.provider.config_file

    @property
    def max_memory_entries(self) -> int:
        return self._config.memory.max_entries

    @property
    def memory_importance_threshold(self) -> float:
        return self._config.memory.importance_threshold

    @property
    def max_conversation_history(self) -> int:
        return self._config.memory.max_conversation_history

    @property
    def rag_enabled(self) -> bool:
        return self._config.rag.enabled

    @property
    def max_rag_results(self) -> int:
        return self._config.rag.max_results

    @property
    def rag_similarity_threshold(self) -> float:
        return self._config.rag.similarity_threshold

    @property
    def require_confirmation(self) -> bool:
        return self._config.safety.require_confirmation

    @property
    def auto_checkpoint(self) -> bool:
        return self._config.safety.auto_checkpoint

    @property
    def max_checkpoints(self) -> int:
        return self._config.safety.max_checkpoints

    @property
    def enable_code_execution(self) -> bool:
        return self._config.tools.enable_code_execution

    @property
    def enable_file_operations(self) -> bool:
        return self._config.tools.enable_file_operations

    @property
    def enable_git_operations(self) -> bool:
        return self._config.tools.enable_git_operations

    @property
    def cli_prompt(self) -> str:
        return self._config.interface.cli_prompt

    @property
    def vibe_code_enabled(self) -> bool:
        return self._config.interface.vibe_code_enabled

    @property
    def installed_agents(self) -> list[str]:
        return self._config.app.installed_agents

    @property
    def connectors(self) -> list[Any]:
        return self._config.tools.connectors

    @property
    def bypass_tool_permissions(self) -> bool:
        return self._config.bypass_tool_permissions

    @property
    def tools(self) -> dict[str, Any]:
        return self._config.tools.model_dump()

    @property
    def agent_paths(self) -> list[Path]:
        return [Path(p) for p in self._config.agent_paths]

    @property
    def enabled_agents(self) -> list[str]:
        return self._config.enabled_agents

    @property
    def disabled_agents(self) -> list[str]:
        return self._config.disabled_agents

    @property
    def max_concurrent_agents(self) -> int:
        return self._config.async_settings.max_concurrent_agents

    @property
    def max_concurrent_tools(self) -> int:
        return self._config.async_settings.max_concurrent_tools

    @property
    def default_timeout(self) -> int:
        return self._config.async_settings.default_timeout

    @property
    def enable_background_tasks(self) -> bool:
        return self._config.async_settings.enable_background_tasks

    @property
    def resource_monitoring(self) -> bool:
        return self._config.async_settings.resource_monitoring

    @property
    def progress_updates(self) -> bool:
        return self._config.async_settings.progress_updates

    # Heartbeat system properties
    @property
    def heartbeat_enabled(self) -> bool:
        return self._config.heartbeat.enabled

    @property
    def heartbeat_interval(self) -> str:
        return self._config.heartbeat.every

    @property
    def heartbeat_target(self) -> str:
        return self._config.heartbeat.target

    @property
    def heartbeat_light_context(self) -> bool:
        return self._config.heartbeat.light_context

    @property
    def heartbeat_isolated_session(self) -> bool:
        return self._config.heartbeat.isolated_session

    @property
    def heartbeat_skip_when_busy(self) -> bool:
        return self._config.heartbeat.skip_when_busy

    @property
    def heartbeat_prompt(self) -> str:
        return self._config.heartbeat.prompt

    @property
    def heartbeat_active_hours(self) -> dict[str, str]:
        return {
            "start": self._config.heartbeat.active_hours.start,
            "end": self._config.heartbeat.active_hours.end,
            "timezone": self._config.heartbeat.active_hours.timezone,
        }

    @property
    def heartbeat_show_ok(self) -> bool:
        return self._config.heartbeat.show_ok

    @property
    def heartbeat_show_alerts(self) -> bool:
        return self._config.heartbeat.show_alerts

    @property
    def heartbeat_use_indicator(self) -> bool:
        return self._config.heartbeat.use_indicator

    # Learning system properties
    @property
    def learning_enabled(self) -> bool:
        return self._config.learning.enabled

    @property
    def skill_creation_threshold(self) -> int:
        return self._config.learning.skill_creation_threshold

    @property
    def self_evaluation_interval(self) -> int:
        return self._config.learning.self_evaluation_interval

    @property
    def memory_dir(self) -> Path:
        return Path(self._config.learning.memory_dir).expanduser()

    @property
    def skills_dir(self) -> Path:
        return Path(self._config.learning.skills_dir).expanduser()

    @property
    def max_memory_chars(self) -> int:
        return self._config.learning.max_memory_chars

    @property
    def max_user_chars(self) -> int:
        return self._config.learning.max_user_chars

    def model_dump(self) -> dict[str, Any]:
        """Return configuration as dictionary"""
        return self._config.model_dump()
