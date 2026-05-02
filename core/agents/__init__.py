"""Agents Package"""

from .base import BaseAgent
from .coding_agent import CodingAgent
from .explore_agent import ExploreAgent
from .plan_agent import PlanAgent

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
    "CodingAgent",
    "ExploreAgent",
    "PlanAgent",
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
