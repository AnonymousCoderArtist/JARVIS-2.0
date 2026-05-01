"""Configuration settings using TOML config file"""

import importlib
import types
from pathlib import Path
from typing import Any, TypeAlias

# Type alias for configuration dictionary
ConfigDict: TypeAlias = dict[str, Any]


def _load_toml_module() -> types.ModuleType:
    try:
        return importlib.import_module("tomllib")
    except ImportError:
        return importlib.import_module("tomli")


class Settings:
    """Application settings loaded from config.toml"""

    def __init__(self, config_path: Path | None = None, initial_config: ConfigDict | None = None):
        self.config_path: Path = config_path or Path("config.toml")
        self._config: ConfigDict = initial_config if initial_config is not None else {}
        if initial_config is None:
            self._load_config()

    def _load_config(self) -> None:
        """Load configuration from TOML file"""
        if self.config_path.exists():
            try:
                toml_module = _load_toml_module()
                with open(self.config_path, "rb") as f:
                    self._config = toml_module.load(f)
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                self._config = self._get_default_config()
        else:
            self._config = self._get_default_config()

    def _get_default_config(self) -> ConfigDict:
        """Get default configuration"""
        return {
            "app": {
                "name": "JARVIS",
                "version": "2.0.0",
                "debug": False,
            },
            "provider": {
                "config_file": "providers.json",
                "selected_provider_id": None,
            },
            "memory": {
                "max_entries": 1000,
                "importance_threshold": 0.5,
                "max_conversation_history": 50,
            },
            "rag": {
                "enabled": True,
                "max_results": 5,
                "similarity_threshold": 0.7,
            },
            "safety": {
                "require_confirmation": True,
                "auto_checkpoint": True,
                "max_checkpoints": 10,
            },
            "tools": {
                "enable_code_execution": True,
                "enable_file_operations": True,
                "enable_git_operations": True,
                # Tool-specific permissions - Vibe-style: read operations always allowed, write operations require approval
                "read": {"permission": "always"},
                "list_dir": {"permission": "always"},
                "glob": {"permission": "always"},
                "grep": {"permission": "always"},
                "read_memory": {"permission": "always"},
                "write": {"permission": "ask"},
                "edit": {"permission": "ask"},
                "bash": {"permission": "ask"},
                "run_tests": {"permission": "ask"},
                "repl": {"permission": "ask"},
                "list_background_processes": {"permission": "ask"},
                "read_background_output": {"permission": "ask"},
                "save_memory": {"permission": "ask"},
                "fetch_webpage": {"permission": "ask"},
                "invoke_agent": {"permission": "ask"},
                "activate_skill": {"permission": "ask"},
                # Vibe-style granular permissions
                "allowlist": [
                    # Always allow files in these patterns
                    "*.md",
                    "*.txt",
                    "*.py",
                    "*.js",
                    "*.ts",
                    "*.json",
                    "*.yaml",
                    "*.yml",
                    "*.toml",
                    "*.cfg",
                    "*.ini",
                ],
                "denylist": [
                    # Never allow files in these patterns
                    "/etc/passwd",
                    "/etc/shadow",
                    "/etc/hosts",
                    "~/.ssh/*",
                    "~/.aws/*",
                    "~/.kube/*",
                    "*.key",
                    "*.pem",
                    "*.p12",
                    "*.pfx",
                ],
                "sensitive_patterns": [
                    # These file patterns require special approval
                    "*secret*",
                    "*password*",
                    "*credential*",
                    "*token*",
                    "*api_key*",
                    "*private_key*",
                    "*.env",
                    "*.env.*",
                    "config/production*",
                    "config/prod*",
                ],
            },
            "interface": {
                "cli_prompt": "JARVIS > ",
            },
            # Permission system settings
            "bypass_tool_permissions": False,
            "agent_paths": [],
            "enabled_agents": [],
            "disabled_agents": [],
        }

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
        """
        Get a configuration value.
        If key is None, it tries to get the value directly from section (top-level key).
        """
        if key is None:
            return self._config.get(section, default)
        
        section_data = self._config.get(section, {})
        if not isinstance(section_data, dict):
            return default
        return section_data.get(key, default)

    def get_section(self, section: str) -> ConfigDict:
        """Get an entire configuration section"""
        data = self._config.get(section, {})
        return data if isinstance(data, dict) else {}

    def set(self, section: str, key: str | None, value: Any = None):
        """
        Set a configuration value.
        If key is None, it sets the value at the top-level (section).
        """
        if key is None:
            self._config[section] = value
            return

        if section not in self._config or not isinstance(self._config[section], dict):
            self._config[section] = {}
        self._config[section][key] = value

    def save(self) -> None:
        """Save configuration to TOML file"""
        try:
            try:
                toml_writer = importlib.import_module("tomli_w")
            except ImportError:
                print("Warning: tomli_w not installed, cannot save config")
                return
            with open(self.config_path, "wb") as f:
                toml_writer.dump(self._config, f)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

    # Convenience properties
    @property
    def app_name(self) -> str:
        return str(self.get("app", "name", "JARVIS"))

    @property
    def app_version(self) -> str:
        return str(self.get("app", "version", "2.0.0"))

    @property
    def debug(self) -> bool:
        return bool(self.get("app", "debug", False))

    @property
    def selected_provider_id(self) -> str | None:
        val = self.get("provider", "selected_provider_id")
        return str(val) if val is not None else None

    @property
    def selected_model_id(self) -> str | None:
        model_cfg = self.get("model", "selected")
        if isinstance(model_cfg, dict):
            return model_cfg.get("id")
        return None

    @property
    def provider_config_file(self) -> str:
        return str(self.get("provider", "config_file", "providers.json"))

    @property
    def max_memory_entries(self) -> int:
        return int(self.get("memory", "max_entries", 1000))

    @property
    def memory_importance_threshold(self) -> float:
        return float(self.get("memory", "importance_threshold", 0.5))

    @property
    def max_conversation_history(self) -> int:
        return int(self.get("memory", "max_conversation_history", 50))

    @property
    def rag_enabled(self) -> bool:
        return bool(self.get("rag", "enabled", True))

    @property
    def max_rag_results(self) -> int:
        return int(self.get("rag", "max_results", 5))

    @property
    def rag_similarity_threshold(self) -> float:
        return float(self.get("rag", "similarity_threshold", 0.7))

    @property
    def require_confirmation(self) -> bool:
        return bool(self.get("safety", "require_confirmation", True))

    @property
    def auto_checkpoint(self) -> bool:
        return bool(self.get("safety", "auto_checkpoint", True))

    @property
    def max_checkpoints(self) -> int:
        return int(self.get("safety", "max_checkpoints", 10))

    @property
    def enable_code_execution(self) -> bool:
        return bool(self.get("tools", "enable_code_execution", True))

    @property
    def enable_file_operations(self) -> bool:
        return bool(self.get("tools", "enable_file_operations", True))

    @property
    def enable_git_operations(self) -> bool:
        return bool(self.get("tools", "enable_git_operations", True))

    @property
    def cli_prompt(self) -> str:
        return str(self.get("interface", "cli_prompt", "JARVIS > "))

    # TUI and Vibe-specific properties
    @property
    def vibe_code_enabled(self) -> bool:
        return bool(self.get("interface", "vibe_code_enabled", False))

    @property
    def installed_agents(self) -> list[str]:
        val = self.get("app", "installed_agents", [])
        return val if isinstance(val, list) else []

    @property
    def connectors(self) -> list[Any]:
        val = self.get("tools", "connectors", [])
        return val if isinstance(val, list) else []

    # Permission system properties
    @property
    def bypass_tool_permissions(self) -> bool:
        return bool(self._config.get("bypass_tool_permissions", False))

    @property
    def tools(self) -> ConfigDict:
        data = self._config.get("tools", {})
        return data if isinstance(data, dict) else {}

    @property
    def agent_paths(self) -> list[Path]:
        paths = self._config.get("agent_paths", [])
        if not isinstance(paths, list):
            return []
        return [Path(p) for p in paths]

    @property
    def enabled_agents(self) -> list[str]:
        val = self._config.get("enabled_agents", [])
        return val if isinstance(val, list) else []

    @property
    def disabled_agents(self) -> list[str]:
        val = self._config.get("disabled_agents", [])
        return val if isinstance(val, list) else []

    def model_dump(self) -> ConfigDict:
        """Return configuration as dictionary"""
        return self._config.copy()
