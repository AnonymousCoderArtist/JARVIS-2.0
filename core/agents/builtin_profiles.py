"""Built-in agent profiles for JARVIS"""

from core.agents.profiles import AgentProfile, AgentSafety, AgentType

# Default agent - Vibe-style: read operations always allowed, write operations require approval, edit tool auto-approved
DEFAULT = AgentProfile(
    name="default",
    display_name="Default",
    description="Read operations always allowed, write operations require approval, edit tool auto-approved",
    safety=AgentSafety.NEUTRAL,
    overrides={
        "tools": {
            "edit": {"permission": "always"},
        }
    },
)

# Plan agent - read-only for exploration and planning
PLAN = AgentProfile(
    name="plan",
    display_name="Plan",
    description="Read-only agent for exploration and planning",
    safety=AgentSafety.SAFE,
    overrides={
        "tools": {
            # Explore-level tools - always allowed
            "read": {"permission": "always"},
            "list_dir": {"permission": "always"},
            "glob": {"permission": "always"},
            "grep": {"permission": "always"},
            # All other tools - disabled
            "write": {"permission": "never"},
            "edit": {"permission": "never"},
            "bash": {"permission": "never"},
            "run_tests": {"permission": "never"},
            "repl": {"permission": "never"},
            "list_background_processes": {"permission": "never"},
            "read_background_output": {"permission": "never"},
            "save_memory": {"permission": "never"},
            "read_memory": {"permission": "never"},
            "fetch_webpage": {"permission": "never"},
            "invoke_agent": {"permission": "never"},
            "activate_skill": {"permission": "never"},
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
        "tools": {
            # Explore-level tools - always allowed
            "read": {"permission": "always"},
            "list_dir": {"permission": "always"},
            "glob": {"permission": "always"},
            "grep": {"permission": "always"},
            # All other tools - disabled
            "write": {"permission": "never"},
            "edit": {"permission": "never"},
            "bash": {"permission": "never"},
            "run_tests": {"permission": "never"},
            "repl": {"permission": "never"},
            "list_background_processes": {"permission": "never"},
            "read_background_output": {"permission": "never"},
            "save_memory": {"permission": "never"},
            "read_memory": {"permission": "never"},
            "fetch_webpage": {"permission": "never"},
            "invoke_agent": {"permission": "never"},
            "activate_skill": {"permission": "never"},
        },
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
