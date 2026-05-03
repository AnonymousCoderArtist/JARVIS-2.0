# Agent Profiles Configuration

JARVIS supports custom agent profiles that can be defined in TOML files. This allows you to create specialized agents with specific safety levels and tool permissions.

## Built-in Agent Profiles

JARVIS comes with the following built-in agent profiles:

### Default
- **Name**: `default`
- **Safety Level**: NEUTRAL
- **Description**: Read operations always allowed, write operations require approval, edit tool auto-approved
- **Best for**: General use with safety checks (Vibe-style approach)
- **Permissions**: Read operations (`read`, `list_dir`, `glob`, `grep`, `read_memory`) are `ALWAYS`, write operations (`write`, `bash`, etc.) are `ASK`, `edit` is `ALWAYS`

### Plan
- **Name**: `plan`
- **Safety Level**: SAFE
- **Description**: Read-only agent for exploration and planning
- **Best for**: Code exploration, planning, and analysis
- **Permissions**: Explore tools (`read`, `list_dir`, `glob`, `grep`) are `ALWAYS`, all others `NEVER`

### Accept Edits
- **Name**: `accept-edits`
- **Safety Level**: DESTRUCTIVE
- **Description**: Auto-approves file edits only
- **Best for**: Code refactoring tasks
- **Permissions**: File write and edit tools are `ALWAYS`, other tools use default `ASK`

### Auto Approve
- **Name**: `auto-approve`
- **Safety Level**: YOLO
- **Description**: Auto-approves all tool executions
- **Best for**: Trusted environments (use with caution)
- **Permissions**: All tools bypass permission checks

### Explore
- **Name**: `explore`
- **Safety Level**: SAFE
- **Description**: Read-only subagent for codebase exploration
- **Best for**: Delegated exploration tasks
- **Type**: Subagent (cannot be selected as primary agent)
- **Permissions**: Explore tools (`read`, `list_dir`, `glob`, `grep`) are `ALWAYS`, all others `NEVER`

## Creating Custom Agent Profiles

Custom agent profiles can be defined in TOML files in the following locations:

1. **User agents directory**: `~/.jarvis/agents/`
2. **Project agents directory**: `.jarvis/agents/` (in your project root)

### Profile Structure

```toml
display_name = "My Custom Agent"
description = "Description of what this agent does"
safety = "neutral"  # Options: safe, neutral, destructive, yolo
agent_type = "agent"  # Options: agent, subagent

# Tool permissions
[tools]
write_file = { permission = "ask" }
edit = { permission = "ask" }
bash = { permission = "never" }
read_file = { permission = "always" }

# Enable only specific tools
enabled_tools = ["read_file", "grep", "find"]

# Disable specific tools
base_disabled = ["bash", "write_file"]

# Bypass tool permissions (use with caution)
bypass_tool_permissions = false

# Custom system prompt
system_prompt_id = "custom_prompt"
```

### Example: Read-Only Documentation Agent

Create `~/.jarvis/agents/documentation.toml`:

```toml
display_name = "Documentation"
description = "Read-only agent for documentation tasks"
safety = "safe"
agent_type = "agent"

[tools]
write_file = { permission = "never" }
edit = { permission = "never" }
bash = { permission = "never" }

enabled_tools = ["read_file", "grep", "find"]
```

### Example: Fast Development Agent

Create `~/.jarvis/agents/fast-dev.toml`:

```toml
display_name = "Fast Dev"
description = "Auto-approves common development tools"
safety = "destructive"
agent_type = "agent"

[tools]
write_file = { permission = "always" }
edit = { permission = "always" }
bash = { permission = "ask" }
read_file = { permission = "always" }
grep = { permission = "always" }
```

## Safety Levels

### SAFE
- **Color**: Green
- **Description**: Read-only operations only
- **Use case**: Exploration, planning, analysis
- **Restrictions**: No file modifications, no command execution

### NEUTRAL
- **Color**: Blue
- **Description**: Requires approval for dangerous operations
- **Use case**: General development
- **Restrictions**: Approval required for file writes, command execution

### DESTRUCTIVE
- **Color**: Orange
- **Description**: Auto-approves file modifications
- **Use case**: Refactoring, bulk edits
- **Restrictions**: File operations auto-approved, commands require approval

### YOLO
- **Color**: Red
- **Description**: Auto-approves everything
- **Use case**: Trusted environments only
- **Restrictions**: No restrictions (use with extreme caution)

## Tool Permissions

### Permission Levels

- **`always`**: Tool executes without asking
- **`never`**: Tool is permanently disabled
- **`ask`**: Tool requires user approval (default)

### Permission Scopes

The permission system supports granular control through:

1. **Tool-level permissions**: Set default behavior for a tool
2. **Session rules**: Temporary permissions for specific patterns
3. **Required permissions**: Fine-grained checks based on tool arguments
4. **Vibe-style granular permissions**:
   - **Path-based allowlist/denylist**: Files matching allowlist patterns are always allowed, denylist patterns are never allowed
   - **Sensitive file patterns**: Files matching sensitive patterns (e.g., *secret*, *.env) require special approval
   - **Workdir boundary**: Files outside working directory require approval
   - **Scratchpad paths**: Files in scratchpad directories are always allowed
   - **Dangerous command patterns**: Bash commands with dangerous patterns (e.g., rm -rf, dd if=) require special approval

### Granular Permission Configuration

The granular permission system is configured in the default settings:

```toml
[tools]
# Tool-level permissions
read = { permission = "always" }
write = { permission = "ask" }
edit = { permission = "ask" }

# Granular path-based permissions
allowlist = [
    "*.md", "*.txt", "*.py", "*.js", "*.ts",
    "*.json", "*.yaml", "*.yml", "*.toml",
]
denylist = [
    "/etc/passwd", "/etc/shadow", "~/.ssh/*",
    "~/.aws/*", "*.key", "*.pem",
]
sensitive_patterns = [
    "*secret*", "*password*", "*credential*",
    "*token*", "*.env", "config/production*",
]
```

### Permission Resolution Flow

For file-based tools, the permission system checks in this order:

1. **Scratchpad Check**: Files in `.jarvis/scratchpad` are always allowed
2. **Denylist Check**: Files matching denylist patterns are never allowed
3. **Allowlist Check**: Files matching allowlist patterns are always allowed
4. **Sensitive Pattern Check**: Files matching sensitive patterns require special approval
5. **Workdir Boundary Check**: Files outside working directory require approval

### Example Tool Configuration

```toml
[tools]
# Always allow reading files
read_file = { permission = "always" }

# Never allow file deletion
delete_file = { permission = "never" }

# Ask before running bash commands
bash = { permission = "ask" }

# Allow specific file patterns
write_file = { permission = "ask", allowlist = ["*.md", "*.txt"] }
```

## Using Custom Profiles

### CLI Usage

```bash
# Start with custom profile
jarvis --agent documentation

# Cycle through profiles in TUI
# Press Shift+Tab to cycle: default → plan → accept-edits → auto-approve
```

### Programmatic Usage

```python
from core.agents.manager import AgentManager
from core.config.settings import Settings

settings = Settings()
agent_manager = AgentManager(
    config_getter=lambda: settings,
    initial_agent="documentation"
)

# Switch to custom profile
agent_manager.switch_profile("fast-dev")
```

## Profile Cycling Order

The default cycling order (Shift+Tab) is:
1. `default`
2. `plan`
3. `accept-edits`
4. `auto-approve`

Custom profiles are added to the end of this list in alphabetical order.

## Best Practices

1. **Start Safe**: Begin with the `default` or `plan` profile
2. **Use Session Rules**: Use "Always allow for this session" for repeated operations
3. **Review Profiles**: Regularly review custom profiles for security
4. **Version Control**: Commit custom profiles to your repository
5. **Document Intent**: Add clear descriptions to custom profiles

## Troubleshooting

### Profile Not Loading
- Check TOML syntax is valid
- Verify file is in correct directory
- Check for duplicate profile names

### Permission Not Working
- Verify tool name matches exactly
- Check if `bypass_tool_permissions` is enabled
- Review session rules that may override settings

### Cycling Not Working
- Ensure profile is not a subagent
- Check if profile is disabled in config
- Verify profile name is unique
