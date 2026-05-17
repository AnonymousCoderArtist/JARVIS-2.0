"""Constants for the agent tool module."""

# Tool names
AGENT_TOOL_NAME = "agents"

# Built-in agent type strings
EXPLORE_AGENT_TYPE = "explore"
PLAN_AGENT_TYPE = "plan"
JARVIS_HELP_AGENT_TYPE = "jarvis-help"
VERIFICATION_AGENT_TYPE = "verification"
STATUSLINE_SETUP_AGENT_TYPE = "statusline-setup"
RUBBER_DUCK_AGENT_TYPE = "rubber-duck"
GENERAL_PURPOSE_AGENT_TYPE = "general-purpose"
FORK_AGENT_TYPE = "fork"

# Built-in one-shot agent types that don't require background execution
ONE_SHOT_BUILTIN_AGENT_TYPES = frozenset({
    EXPLORE_AGENT_TYPE,
    PLAN_AGENT_TYPE,
    JARVIS_HELP_AGENT_TYPE,
    VERIFICATION_AGENT_TYPE,
    STATUSLINE_SETUP_AGENT_TYPE,
    RUBBER_DUCK_AGENT_TYPE,
})

# Tool allowlists for different agent types
EXPLORE_ALLOWED_TOOLS = ("read", "ls", "find", "grep")
PLAN_ALLOWED_TOOLS = ("read", "ls", "find", "grep", "web_search", "fetch_webpage", "save_memory", "read_memory")
JARVIS_HELP_ALLOWED_TOOLS = ("read", "ls", "find", "grep", "web_search", "fetch_webpage")
VERIFICATION_ALLOWED_TOOLS = ("bash", "read", "ls", "find", "grep", "web_search", "fetch_webpage")
STATUSLINE_SETUP_ALLOWED_TOOLS = ("read", "ls", "find", "grep", "web_search", "fetch_webpage")
RUBBER_DUCK_ALLOWED_TOOLS = ("read", "ls", "find", "grep", "bash(read-only)", "web_search", "fetch_webpage")

# Default max tokens for background agents
DEFAULT_MAX_TOKENS = 128000
