"""Built-in agent profiles for JARVIS"""

from core.agents.profiles import AgentProfile, AgentSafety, AgentType

# Default agent - Ask for permission for ALL tools
DEFAULT = AgentProfile(
    name="default",
    display_name="Default",
    description="Ask for permission for all tools",
    safety=AgentSafety.NEUTRAL,
    overrides={
        "tools": {
            # File tools
            "read": {"permission": "ask"},
            "write_file": {"permission": "ask"},
            "edit": {"permission": "ask"},
            "ls": {"permission": "ask"},
            "find": {"permission": "ask"},
            # Search tools
            "grep": {"permission": "ask"},
            # Code tools
            "bash": {"permission": "ask"},
            "run_tests": {"permission": "ask"},
            "repl": {"permission": "ask"},
            # Background tools
            "list_background_processes": {"permission": "ask"},
            "read_background_output": {"permission": "ask"},
            # Memory tools
            "save_memory": {"permission": "ask"},
            "read_memory": {"permission": "ask"},
            # Web tools
            "fetch_webpage": {"permission": "ask"},
            "web_search": {"permission": "ask"},
            # Agent tools
            "agents": {"permission": "ask"},
            "activate_skill": {"permission": "ask"},
            "agent_status": {"permission": "ask"},
        }
    },
)

# Plan agent - read-only for exploration and planning
PLAN = AgentProfile(
    name="plan",
    display_name="Plan",
    description="Read-only agent for exploration and planning",
    safety=AgentSafety.SAFE,
    agent_type=AgentType.SUBAGENT,
    overrides={
        "tools": {
            # Explore-level tools - always allowed
            "read": {"permission": "always"},
            "ls": {"permission": "always"},
            "find": {"permission": "always"},
            "grep": {"permission": "always"},
            # All other tools - disabled
            "write": {"permission": "never"},
            "edit": {"permission": "never"},
            "bash": {"permission": "never"},
            "run_tests": {"permission": "never"},
            "repl": {"permission": "never"},
            "list_background_processes": {"permission": "never"},
            "read_background_output": {"permission": "never"},
            "save_memory": {"permission": "always"},
            "read_memory": {"permission": "always"},
            "fetch_webpage": {"permission": "always"},
            "web_search": {"permission": "always"},
            "agents": {"permission": "never"},
            "activate_skill": {"permission": "never"},
            "agent_status": {"permission": "never"},
        },
        "system_prompt_id": "plan",
    },
)

# Accept Edits agent - edit, write, read, glob, grep always; others ask
ACCEPT_EDITS = AgentProfile(
    name="accept-edits",
    display_name="Accept Edits",
    description="edit, write, read, glob, grep always; others ask from user",
    safety=AgentSafety.DESTRUCTIVE,
    overrides={
        "tools": {
            # File operations - always allowed
            "edit": {"permission": "always"},
            "write_file": {"permission": "always"},
            "read": {"permission": "always"},
            # Search operations - always allowed
            "find": {"permission": "always"},
            "grep": {"permission": "always"},
            "ls": {"permission": "always"},
            # Code tools - ask
            "bash": {"permission": "ask"},
            "run_tests": {"permission": "ask"},
            "repl": {"permission": "ask"},
            # Background tools - ask
            "list_background_processes": {"permission": "ask"},
            "read_background_output": {"permission": "ask"},
            # Memory tools - ask
            "save_memory": {"permission": "ask"},
            "read_memory": {"permission": "ask"},
            # Web tools - ask
            "fetch_webpage": {"permission": "ask"},
            "web_search": {"permission": "ask"},
            # Agent tools - ask
            "agents": {"permission": "ask"},
            "activate_skill": {"permission": "ask"},
            "agent_status": {"permission": "ask"},
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

# Explore agent - all tools always except bash, edit, and subagent tools
EXPLORE = AgentProfile(
    name="explore",
    display_name="Explore",
    description="All tools always except bash, edit, and subagent tools",
    safety=AgentSafety.SAFE,
    agent_type=AgentType.SUBAGENT,
    overrides={
        "tools": {
            # File tools - always
            "read": {"permission": "always"},
            "write_file": {"permission": "always"},
            "edit": {"permission": "never"},  # Excluded
            "ls": {"permission": "always"},
            "find": {"permission": "always"},
            # Search tools - always
            "grep": {"permission": "always"},
            # Code tools - bash excluded, others always
            "bash": {"permission": "never"},  # Excluded
            "run_tests": {"permission": "always"},
            "repl": {"permission": "always"},
            # Background tools - always
            "list_background_processes": {"permission": "always"},
            "read_background_output": {"permission": "always"},
            # Memory tools - always
            "save_memory": {"permission": "always"},
            "read_memory": {"permission": "always"},
            # Web tools - always
            "fetch_webpage": {"permission": "always"},
            "web_search": {"permission": "always"},
            # Agent tools - excluded (subagent tools)
            "agents": {"permission": "never"},  # Excluded
            "activate_skill": {"permission": "never"},  # Excluded
            "agent_status": {"permission": "never"},  # Excluded
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
