"""Built-in agent profiles for JARVIS"""

from core.agents.profiles import AgentProfile, AgentSafety, AgentType

# Default agent - requires approval for tool executions
DEFAULT = AgentProfile(
    name="default",
    display_name="Default",
    description="Requires approval for tool executions",
    safety=AgentSafety.NEUTRAL,
    overrides={},
)

# Plan agent - read-only for exploration and planning
PLAN = AgentProfile(
    name="plan",
    display_name="Plan",
    description="Read-only agent for exploration and planning",
    safety=AgentSafety.SAFE,
    overrides={
        "tools": {
            "write_file": {"permission": "never"},
            "edit": {"permission": "never"},
        }
    },
)

# Accept Edits agent - auto-approves file edits only
ACCEPT_EDITS = AgentProfile(
    name="accept-edits",
    display_name="Accept Edits",
    description="Auto-approves file edits only",
    safety=AgentSafety.DESTRUCTIVE,
    overrides={
        "tools": {
            "write_file": {"permission": "always"},
            "edit": {"permission": "always"},
        }
    },
)

# Auto Approve agent - auto-approves all tool executions
AUTO_APPROVE = AgentProfile(
    name="auto-approve",
    display_name="Auto Approve",
    description="Auto-approves all tool executions",
    safety=AgentSafety.YOLO,
    overrides={"bypass_tool_permissions": True},
)

# Explore agent - read-only subagent for codebase exploration
EXPLORE = AgentProfile(
    name="explore",
    display_name="Explore",
    description="Read-only subagent for codebase exploration",
    safety=AgentSafety.SAFE,
    agent_type=AgentType.SUBAGENT,
    overrides={
        "enabled_tools": ["grep", "read_file", "glob"],
        "system_prompt_id": "explore",
    },
)

# Dictionary of built-in agents
BUILTIN_AGENTS: dict[str, AgentProfile] = {
    "default": DEFAULT,
    "plan": PLAN,
    "accept-edits": ACCEPT_EDITS,
    "auto-approve": AUTO_APPROVE,
    "explore": EXPLORE,
}

# Agent cycling order
AGENT_ORDER = ["default", "plan", "accept-edits", "auto-approve"]
