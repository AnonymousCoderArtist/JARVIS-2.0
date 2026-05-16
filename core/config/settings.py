"""Configuration settings using JSON config files with layered deep-merge.

Configuration precedence (lowest → highest):
1. Defaults (hard-coded in ``JarvisSettings`` model)
2. ``~/.jarvis/settings.json`` (user global)
3. ``.jarvis/settings.json`` (project-specific)
4. Environment variables (``JARVIS_*``)
5. Runtime ``initial_config`` parameter

Unknown keys from all JSON sources are **preserved** so that extensions
can store their own configuration without schema validation errors.

Concurrent access is safe via ``filelock``.
"""

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


def _acquire_lock(lock_path: Path, timeout: float = 5.0) -> Any:
    """Try to acquire a file lock, returns a lock handle or None."""
    try:
        import filelock
        lock = filelock.FileLock(lock_path, timeout=timeout)
        lock.acquire()
        return lock
    except ImportError:
        # filelock not installed — skip locking
        return None
    except Exception:
        return None


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
            config_paths = [Path(config_path)]
            self._config_path = config_paths[-1]
        else:
            config_paths = _get_default_config_paths()
            self._config_path = config_paths[-1] if config_paths else Path(".jarvis") / "settings.json"

        self._config_paths = config_paths
        self._lock: Any = None
        self._raw_extras: dict[str, Any] = {}  # Unknown keys from JSON

        # Load and merge
        self._load_and_merge(config_paths, initial_config)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_and_merge(
        self,
        config_paths: list[Path],
        initial_config: dict[str, Any] | None = None,
    ) -> None:
        """Load JSON from *config_paths* (lowest → highest), merge with env + runtime."""
        # 1. Start with empty
        merged: dict[str, Any] = {}
        self._raw_extras = {}

        # 2. Load JSON in order
        for path in config_paths:
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        loaded: dict = json.load(f)
                        merged = self._deep_merge(merged, loaded)
                        # Collect unknown keys for preservation
                        self._raw_extras = self._deep_merge(self._raw_extras, loaded)
                except Exception as e:
                    print(f"Warning: Failed to load config from {path}: {e}")

        # 3. Override with environment
        env_config = _load_env_config()
        merged = self._deep_merge(merged, env_config)

        # 4. Override with runtime initial_config
        if initial_config:
            merged = self._deep_merge(merged, initial_config)

        # 5. Apply to Pydantic model (unknown keys are silently ignored by Pydantic
        #    but preserved in _raw_extras for get_raw / get_extension_config)
        self._config: JarvisSettings = JarvisSettings(**(merged or {}))

    def reload(self) -> None:
        """Hot-reload settings from disk. Call this after file changes."""
        self._load_and_merge(self._config_paths)

    # ------------------------------------------------------------------
    # Merging
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

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

    def get_extension_config(self, extension_name: str) -> dict[str, Any]:
        """Get extension-specific configuration from the ``extensions`` section.

        Extensions can store their config in ``.jarvis/settings.json`` under::

            {
              "extensions": {
                "my_extension": { "host": "...", "key": "..." }
              }
            }
        """
        extensions = getattr(self._config, "extensions", None)
        if isinstance(extensions, dict):
            return extensions.get(extension_name, {})
        return {}

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
        data = self._config.model_dump()
        # Re-inject preserved unknown keys
        for key, value in self._raw_extras.items():
            if key not in data:
                data[key] = value
        return data

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Save configuration to the highest-priority JSON file.

        Uses file-locking (via ``filelock`` if available) to prevent
        concurrent write corruption between multiple JARVIS instances.
        """
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self._config_path.with_suffix(".lock")

            lock = _acquire_lock(lock_path)
            try:
                data = self.model_dump()
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            finally:
                if lock is not None:
                    try:
                        lock.release()
                    except Exception:
                        pass
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

