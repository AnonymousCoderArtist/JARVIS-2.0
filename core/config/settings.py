"""Configuration settings using TOML config file"""

import importlib
import sys
from pathlib import Path
from typing import Any

from core.config.models import JarvisSettings

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class Settings:
    """Application settings loaded from config.toml"""

    def __init__(self, config_path: Path | None = None, initial_config: dict[str, Any] | None = None):
        self.config_path: Path = config_path or Path("config.toml")
        self._config: JarvisSettings = JarvisSettings(**(initial_config or {}))
        if initial_config is None:
            self._load_config()

    def _load_config(self) -> None:
        """Load configuration from TOML file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "rb") as f:
                    data = tomllib.load(f)
                    self._config = JarvisSettings(**data)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
        # Defaults are handled by Pydantic factories

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

    def model_dump(self) -> dict[str, Any]:
        """Return configuration as dictionary"""
        return self._config.model_dump()
