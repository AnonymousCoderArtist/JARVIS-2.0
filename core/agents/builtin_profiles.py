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

# Plan agent - sub-agent with read-only tools always allowed
PLAN = AgentProfile(
    name="plan",
    display_name="Plan",
    description="Sub-agent for exploration and planning (read-only tools always allowed)",
    safety=AgentSafety.SAFE,
    agent_type=AgentType.SUBAGENT,
    overrides={
        "tools": {
            # File tools - read only always, write/edit never
            "read": {"permission": "always"},
            "write_file": {"permission": "never"},
            "edit": {"permission": "never"},
            "ls": {"permission": "always"},
            "find": {"permission": "always"},
            # Search tools - always allowed
            "grep": {"permission": "always"},
            # Code tools - never
            "bash": {"permission": "never"},
            "run_tests": {"permission": "never"},
            "repl": {"permission": "never"},
            # Background tools - read only always
            "list_background_processes": {"permission": "always"},
            "read_background_output": {"permission": "always"},
            # Memory tools - read always, save never
            "save_memory": {"permission": "never"},
            "read_memory": {"permission": "always"},
            # Web tools - always allowed (read-only)
            "fetch_webpage": {"permission": "always"},
            "web_search": {"permission": "always"},
            # Agent tools - never for safety
            "agents": {"permission": "never"},
            "activate_skill": {"permission": "never"},
            "agent_status": {"permission": "always"},
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

# Explore agent - sub-agent with read-only tools always allowed
EXPLORE = AgentProfile(
    name="explore",
    display_name="Explore",
    description="Sub-agent for codebase exploration (read-only tools always allowed)",
    safety=AgentSafety.SAFE,
    agent_type=AgentType.SUBAGENT,
    overrides={
        "tools": {
            # File tools - read only always, write/edit never
            "read": {"permission": "always"},
            "write_file": {"permission": "never"},
            "edit": {"permission": "never"},
            "ls": {"permission": "always"},
            "find": {"permission": "always"},
            # Search tools - always allowed
            "grep": {"permission": "always"},
            # Code tools - never
            "bash": {"permission": "never"},
            "run_tests": {"permission": "never"},
            "repl": {"permission": "never"},
            # Background tools - read only always
            "list_background_processes": {"permission": "always"},
            "read_background_output": {"permission": "always"},
            # Memory tools - read always, save never
            "save_memory": {"permission": "never"},
            "read_memory": {"permission": "always"},
            # Web tools - always allowed (read-only)
            "fetch_webpage": {"permission": "always"},
            "web_search": {"permission": "always"},
            # Agent tools - never for safety
            "agents": {"permission": "never"},
            "activate_skill": {"permission": "never"},
            "agent_status": {"permission": "always"},
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
