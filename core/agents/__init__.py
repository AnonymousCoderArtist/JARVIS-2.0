"""Agents Package"""

from .agent_definition import AgentDefinition
from .base import BaseAgent
from .builtin.jarvis_help_agent import JARVIS_HELP_AGENT, JarvisHelpAgent
from .builtin.statusline_setup_agent import STATUSLINE_SETUP_AGENT
from .builtin.verification_agent import VERIFICATION_AGENT, VerificationAgent
from .builtin_profiles import (
    ACCEPT_EDITS,
    AGENT_ORDER,
    AUTO_APPROVE,
    BUILTIN_AGENTS,
    DEFAULT,
    EXPLORE,
    PLAN,
)
from .explore_agent import ExploreAgent
from .jarvis_v2 import JarvisV2
from .manager import AgentManager
from .plan_agent import PlanAgent
from .profiles import AgentProfile, AgentSafety, AgentType

# Backwards compatibility alias
CodingAgent = JarvisV2

# Cowork imports - lazy loaded to avoid circular imports
# These are available but imported lazily when accessed via __getattr__
_COWORK_IMPORTS = {
    "CoworkAgent", "CoworkConfig", "CoworkMemory", "SandboxManager",
    "TaskScheduler", "COWORK_SYSTEM_PROMPT", "get_cowork_metadata"
}


def __getattr__(name: str):
    """Lazy load cowork modules to break circular import chain."""
    if name in _COWORK_IMPORTS:
        if name == "COWORK_SYSTEM_PROMPT":
            from .cowork.prompts.system_prompt import COWORK_SYSTEM_PROMPT
            globals()["COWORK_SYSTEM_PROMPT"] = COWORK_SYSTEM_PROMPT
            return COWORK_SYSTEM_PROMPT
        if name == "get_cowork_metadata":
            from .cowork.prompts.system_prompt import get_cowork_metadata
            globals()["get_cowork_metadata"] = get_cowork_metadata
            return get_cowork_metadata
        if name == "CoworkAgent":
            from .cowork import CoworkAgent
            globals()["CoworkAgent"] = CoworkAgent
            return CoworkAgent
        if name == "CoworkConfig":
            from .cowork import CoworkConfig
            globals()["CoworkConfig"] = CoworkConfig
            return CoworkConfig
        if name == "CoworkMemory":
            from .cowork.memory import CoworkMemory
            globals()["CoworkMemory"] = CoworkMemory
            return CoworkMemory
        if name == "SandboxManager":
            from .cowork.sandbox import SandboxManager
            globals()["SandboxManager"] = SandboxManager
            return SandboxManager
        if name == "TaskScheduler":
            from .cowork.task_scheduler import TaskScheduler
            globals()["TaskScheduler"] = TaskScheduler
            return TaskScheduler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Note: Agent classes (JarvisHelpAgent, VerificationAgent) are imported separately
# Agent definitions (JARVIS_HELP_AGENT, VERIFICATION_AGENT, STATUSLINE_SETUP_AGENT)
# are imported by builtin_agents.py via the builtin/__init__.py modules

__all__ = [
    "BaseAgent",
    "JarvisV2",
    "CodingAgent",  # Backwards compatibility alias
    "ExploreAgent",
    "PlanAgent",
    "CoworkAgent",
    "JarvisHelpAgent",
    "VerificationAgent",
    # Agent definitions
    "JARVIS_HELP_AGENT",
    "VERIFICATION_AGENT",
    "STATUSLINE_SETUP_AGENT",
    # Agent definition class
    "AgentDefinition",
    # Profile system
    "AgentProfile",
    "AgentSafety",
    "AgentType",
    "AgentManager",
    "BUILTIN_AGENTS",
    "AGENT_ORDER",
    "DEFAULT",
    "PLAN",
    "ACCEPT_EDITS",
    "AUTO_APPROVE",
    "EXPLORE",
    "CoworkConfig",
    "CoworkMemory",
    "SandboxManager",
    "TaskScheduler",
    "COWORK_SYSTEM_PROMPT",
    "get_cowork_metadata",
]
