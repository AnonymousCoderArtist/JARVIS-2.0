"""Built-in agent profiles for JARVIS"""

from core.agents.profiles import AgentProfile, AgentSafety, AgentType

# Default agent - Ask for permission for ALL tools
DEFAULT = AgentProfile(
    name="default",
    display_name="Default",
    description="Ask for permission for all tools",
    safety=AgentSafety.NEUTRAL,
    overrides={
        "disallowed_tools": [],  # No disallowed tools, all require permission
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
        },
    },
)

# Plan agent - sub-agent with read-only tools always allowed
PLAN = AgentProfile(
    name="plan",
    display_name="Plan",
    description="Sub-agent for exploration and planning (read-only tools always allowed)",
    safety=AgentSafety.SAFE,
    agent_type=AgentType.SUBAGENT,
    tools=["read", "ls", "find", "grep", "web_search", "fetch_webpage", "save_memory", "read_memory"],
    overrides={
        "disallowed_tools": ['write_file', 'edit', 'bash', 'run_tests', 'repl', 'agents', 'activate_skill', 'save_memory'],
        "tools": {
            # Read-only tools - always allowed
            "read": {"permission": "always"},
            "ls": {"permission": "always"},
            "find": {"permission": "always"},
            "grep": {"permission": "always"},
            # Background tools - read only always
            "list_background_processes": {"permission": "always"},
            "read_background_output": {"permission": "always"},
            # Memory tools - read always
            "read_memory": {"permission": "always"},
            # Web tools - always allowed (read-only)
            "fetch_webpage": {"permission": "always"},
            "web_search": {"permission": "always"},
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
    tools=["read", "write_file", "edit", "ls", "find", "grep"],
    overrides={
        "disallowed_tools": ['bash', 'run_tests', 'repl', 'activate_skill', 'agents', 'save_memory', 'web_search', 'fetch_webpage'],
        "tools": {
            # File operations - always allowed
            "edit": {"permission": "always"},
            "write_file": {"permission": "always"},
            "read": {"permission": "always"},
            # Search operations - always allowed
            "find": {"permission": "always"},
            "grep": {"permission": "always"},
            "ls": {"permission": "always"},
        },
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
    tools=["read", "ls", "find", "grep"],
    overrides={
        "disallowed_tools": ['write_file', 'edit', 'bash', 'run_tests', 'repl', 'agents', 'activate_skill', 'save_memory'],
        "tools": {
            # Read-only tools - always allowed
            "read": {"permission": "always"},
            "ls": {"permission": "always"},
            "find": {"permission": "always"},
            "grep": {"permission": "always"},
            # Background tools - read only always
            "list_background_processes": {"permission": "always"},
            "read_background_output": {"permission": "always"},
            # Memory tools - read always
            "read_memory": {"permission": "always"},
            # Web tools - always allowed (read-only)
            "fetch_webpage": {"permission": "always"},
            "web_search": {"permission": "always"},
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
