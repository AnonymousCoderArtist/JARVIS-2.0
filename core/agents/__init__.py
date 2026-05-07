"""Agents Package"""

from .base import BaseAgent
from .jarvis_v2 import JarvisV2
from .explore_agent import ExploreAgent
from .plan_agent import PlanAgent
from .builtin.jarvis_help_agent import JarvisHelpAgent, JARVIS_HELP_AGENT
from .builtin.verification_agent import VerificationAgent, VERIFICATION_AGENT
from .builtin.statusline_setup_agent import STATUSLINE_SETUP_AGENT

# Backwards compatibility alias
CodingAgent = JarvisV2

# Note: Agent classes (JarvisHelpAgent, VerificationAgent) are imported separately
# Agent definitions (JARVIS_HELP_AGENT, VERIFICATION_AGENT, STATUSLINE_SETUP_AGENT)
# are imported by builtin_agents.py via the builtin/__init__.py module

# Agent definition export
from .agent_definition import AgentDefinition

# Agent profile system
from .builtin_profiles import (
    ACCEPT_EDITS,
    AGENT_ORDER,
    AUTO_APPROVE,
    BUILTIN_AGENTS,
    DEFAULT,
    EXPLORE,
    PLAN,
)
from .manager import AgentManager
from .profiles import AgentProfile, AgentSafety, AgentType

__all__ = [
    "BaseAgent",
    "JarvisV2",
    "CodingAgent",  # Backwards compatibility alias
    "ExploreAgent",
    "PlanAgent",
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
]
