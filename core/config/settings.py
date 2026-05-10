"""Configuration settings using JSON config files"""

import json
import os
from pathlib import Path
from typing import Any

from core.config.models import JarvisSettings


def _get_default_config_paths() -> list[Path]:
    """Get default configuration file paths in order of precedence.
    
    Priority (lowest to highest):
    1. ~/.jarvis/settings.json (global defaults)
    2. .jarvis/settings.json (project-specific overrides)
    """
    home_settings = Path.home() / ".jarvis" / "settings.json"
    project_settings = Path(".jarvis") / "settings.json"
    return [home_settings, project_settings]


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
    """Application settings loaded from JSON config files with environment variable overrides.
    
    Configuration precedence (lowest to highest):
    1. ~/.jarvis/settings.json (global defaults)
    2. .jarvis/settings.json (project-specific overrides)
    3. Environment variables
    4. initial_config parameter
    """

    def __init__(self, config_path: Path | None = None, initial_config: dict[str, Any] | None = None):
        # Determine config paths to load
        if config_path:
            # Single explicit path
            config_paths = [Path(config_path)]
            self._config_path = config_paths[0]
        else:
            # Default: search in order of precedence
            config_paths = _get_default_config_paths()
            # Use the highest priority path (last one) as the config_path for save()
            self._config_path = config_paths[-1] if config_paths else Path(".jarvis") / "settings.json"

        # Load JSON configs in order (lowest to highest priority)
        json_config: dict[str, Any] = {}
        for path in config_paths:
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        loaded = json.load(f)
                        json_config = self._deep_merge(json_config, loaded)
                except Exception as e:
                    print(f"Warning: Failed to load config from {path}: {e}")

        # Override with environment config
        env_config = _load_env_config()

        # Merge: start with json, then env, then initial_config
        merged_config = self._deep_merge(json_config, env_config)
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

    def model_dump(self) -> dict[str, Any]:
        """Convert config to dictionary for agent lifecycle."""
        return self._config.model_dump()

    def save(self) -> None:
        """Save configuration to JSON file"""
        try:
            # Ensure parent directory exists
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config.model_dump(), f, indent=4)
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
    def installed_agents(self) -> list[str]:
        return self._config.app.installed_agents

    @property
    def connectors(self) -> list[Any]:
        return self._config.tools.connectors

    @property
    def bypass_tool_permissions(self) -> bool:
        return self._config.bypass_tool_permissions

    @property
    def disallowed_tools(self) -> list[str]:
        return self._config.disallowed_tools

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
    def vibe_code_enabled(self) -> bool:
        return self._config.vibe_code_enabled

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

    # Sandbox settings
    @property
    def sandbox_enabled(self) -> bool:
        return self._config.sandbox.enabled

    @property
    def sandbox_backend(self) -> str:
        return self._config.sandbox.backend

    @property
    def sandbox_base_url(self) -> str:
        return self._config.sandbox.base_url

    @property
    def sandbox_timeout(self) -> int:
        return self._config.sandbox.timeout

    @property
    def sandbox_runtime(self) -> str:
        return self._config.sandbox.runtime

    