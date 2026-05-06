"""Agent manager for profile switching and discovery"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from core.agents.builtin_profiles import AGENT_ORDER, BUILTIN_AGENTS
from core.agents.profiles import AgentProfile, AgentType

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.config.settings import Settings


class AgentManager:
    """Manages agent profiles and switching"""

    def __init__(
        self,
        config_getter: Callable[[], Settings],
        initial_agent: str = "default",
        allow_subagent: bool = False,
    ):
        """
        Initialize agent manager

        Args:
            config_getter: Function to get current configuration
            initial_agent: Name of initial agent profile
            allow_subagent: Whether subagents can be selected as primary agent
        """
        self._config_getter = config_getter
        self._search_paths = self._compute_search_paths(self._config)
        self._available = self._discover_agents()

        custom_count = len(self._available) - len(BUILTIN_AGENTS)
        if custom_count > 0:
            custom_names = [
                name
                for name in self._available
                if name not in BUILTIN_AGENTS
            ]
            logger.info(
                "Discovered custom agents %s in %s",
                " ".join(custom_names),
                " ".join(str(p) for p in self._search_paths),
            )

        profile = self._available.get(initial_agent)
        if (
            not allow_subagent
            and profile is not None
            and profile.agent_type != AgentType.AGENT
        ):
            raise ValueError(
                f"Agent '{initial_agent}' is a {profile.agent_type} and cannot be used"
                f" as the primary agent. Only agents of type 'agent' can be selected"
                f" with --agent."
            )

        self.active_profile = profile or self._available["default"]
        self._cached_config: Settings | None = None

    @property
    def _config(self) -> Settings:
        """Get current configuration"""
        return self._config_getter()

    @property
    def available_agents(self) -> dict[str, AgentProfile]:
        """Get available agents based on configuration"""
        base = self._available.copy()

        # Filter by enabled_agents if specified
        if self._config.enabled_agents:
            return {
                name: profile
                for name, profile in base.items()
                if self._name_matches(name, self._config.enabled_agents)
            }

        # Filter by disabled_agents if specified
        if self._config.disabled_agents:
            return {
                name: profile
                for name, profile in base.items()
                if not self._name_matches(name, self._config.disabled_agents)
            }

        return base

    @property
    def config(self) -> Settings:
        """Get configuration with active profile applied"""
        from core.config.settings import Settings
        
        if self._cached_config is None:
            merged_dict = self.active_profile.apply_to_config(
                self._config.model_dump()
            )
            self._cached_config = Settings(initial_config=merged_dict)
        return self._cached_config

    def switch_profile(self, name: str) -> None:
        """
        Switch to a different agent profile

        Args:
            name: Name of the profile to switch to
        """
        self.active_profile = self.get_agent(name)
        self._cached_config = None

    def register_agent(self, profile: AgentProfile) -> None:
        """
        Register a custom agent profile

        Args:
            profile: Agent profile to register
        """
        self._available[profile.name] = profile
        self._cached_config = None

    def invalidate_config(self) -> None:
        """Invalidate cached configuration"""
        self._cached_config = None

    @staticmethod
    def _compute_search_paths(config: Settings) -> list[Path]:
        """Compute search paths for agent discovery"""
        paths: list[Path] = []

        # Add configured agent paths
        for path in config.agent_paths:
            if path.is_dir():
                paths.append(path)

        # Add user agents directory
        user_agents_dir = Path.home() / ".jarvis" / "agents"
        if user_agents_dir.is_dir():
            paths.append(user_agents_dir)

        # Add project agents directory
        project_agents_dir = Path.cwd() / ".jarvis" / "agents"
        if project_agents_dir.is_dir():
            paths.append(project_agents_dir)

        # Remove duplicates while preserving order
        unique: list[Path] = []
        for p in paths:
            rp = p.resolve()
            if rp not in unique:
                unique.append(rp)

        return unique

    def _discover_agents(self) -> dict[str, AgentProfile]:
        """Discover built-in and custom agents"""
        agents: dict[str, AgentProfile] = dict(BUILTIN_AGENTS)

        for base in self._search_paths:
            if not base.is_dir():
                continue

            for agent_file in base.glob("*.toml"):
                if not agent_file.is_file():
                    continue

                agent = self._try_load_agent(agent_file)
                if agent is not None:
                    if agent.name in BUILTIN_AGENTS:
                        logger.info(
                            "Custom agent '%s' overrides builtin agent", agent.name
                        )
                    elif agent.name in agents:
                        logger.debug(
                            "Skipping duplicate agent '%s' at %s",
                            agent.name,
                            agent_file,
                        )
                        continue

                    agents[agent.name] = agent

        return agents

    def _try_load_agent(self, agent_file: Path) -> AgentProfile | None:
        """Try to load an agent profile from a TOML file"""
        try:
            agent = AgentProfile.from_toml(str(agent_file))
            agent.apply_to_config(self._config.model_dump())
            return agent
        except Exception as e:
            logger.warning("Failed to load agent at %s: %s", agent_file, e)
            return None

    def get_agent(self, name: str) -> AgentProfile:
        """
        Get an agent profile by name

        Args:
            name: Name of the agent

        Returns:
            AgentProfile instance

        Raises:
            ValueError: If agent not found
        """
        if agent := self.available_agents.get(name):
            return agent
        raise ValueError(f"Agent '{name}' not found")

    def get_subagents(self) -> list[AgentProfile]:
        """Get all subagent profiles"""
        return [
            a for a in self.available_agents.values() if a.agent_type == AgentType.SUBAGENT
        ]

    def get_all_agents(self) -> list[dict[str, str]]:
        """Get all agents as list of dicts for UI display."""
        return [
            {"name": name, "display_name": profile.display_name}
            for name, profile in self.available_agents.items()
        ]

    def get_agent_order(self) -> list[str]:
        """Get ordered list of agents for cycling"""
        primary_agents = [
            name
            for name, agent in self.available_agents.items()
            if agent.agent_type == AgentType.AGENT
        ]

        # Start with builtin order, then add custom agents
        order = [name for name in AGENT_ORDER if name in primary_agents]
        custom = sorted(
            name for name in primary_agents if name not in AGENT_ORDER
        )
        return order + custom

    def next_agent(self, current: AgentProfile) -> AgentProfile:
        """
        Get next agent in cycling order

        Args:
            current: Current agent profile

        Returns:
            Next agent profile
        """
        order = self.get_agent_order()
        idx = (
            order.index(current.name)
            if current.name in order
            else -1
        )
        return self.available_agents[order[(idx + 1) % len(order)]]

    @staticmethod
    def _name_matches(name: str, patterns: list[str]) -> bool:
        """Check if agent name matches any pattern"""
        import fnmatch

        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    def list_profiles(self) -> list[str]:
        """List all available profile names"""
        return list(self.available_agents.keys())

    def get_current_profile(self) -> str:
        """Get the current profile name"""
        return self.active_profile.name
