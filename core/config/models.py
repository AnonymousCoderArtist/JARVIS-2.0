from typing import Any

from pydantic import BaseModel, Field


class ActiveHoursSettings(BaseModel):
    """Active hours configuration for heartbeat"""
    start: str = "08:00"
    end: str = "22:00"
    timezone: str = "America/New_York"


class HeartbeatSettings(BaseModel):
    """Heartbeat system configuration"""
    enabled: bool = False
    every: str = "30m"  # e.g., "30m", "1h", "15m"
    target: str = "last"  # "last", "none", or channel name
    light_context: bool = False
    isolated_session: bool = False
    skip_when_busy: bool = False
    active_hours: ActiveHoursSettings = Field(default_factory=ActiveHoursSettings)
    prompt: str = "Read HEARTBEAT.md if exists. Follow strictly. If nothing needs attention, reply HEARTBEAT_OK."
    ack_max_chars: int = 300
    show_ok: bool = True
    show_alerts: bool = True
    use_indicator: bool = True


class LearningSettings(BaseModel):
    """Learning loop configuration"""
    enabled: bool = False
    skill_creation_threshold: int = 5  # Create skill after this many tool calls
    self_evaluation_interval: int = 15  # Self-eval checkpoint every N tool calls
    memory_dir: str = "~/.jarvis/memory"
    skills_dir: str = "~/.jarvis/skills"


class SandboxSettings(BaseModel):
    """Sandbox execution settings for shell commands"""
    enabled: bool = False
    backend: str = "bwrap"  # "bwrap" (bubblewrap), "opensandbox", "disabled"
    base_url: str = "http://localhost:8080"
    timeout: int = 30
    runtime: str = "opensandbox/code-interpreter:v1.0.2"


class AppSettings(BaseModel):
    name: str = "JARVIS"
    version: str = "2.0.0"
    debug: bool = False
    installed_agents: list[str] = Field(default_factory=list)


class ProviderSettings(BaseModel):
    config_file: str = "providers.json"
    selected_provider_id: str | None = None


class ToolPermissions(BaseModel):
    permission: str = "ask"


class ToolSettings(BaseModel):
    enable_code_execution: bool = True
    enable_file_operations: bool = True
    enable_git_operations: bool = True

    # Tool permissions
    read: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
    ls: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
    find: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
    list_dir: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
    glob: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
    grep: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
    read_memory: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))

    # Sensitive operations
    write: ToolPermissions = Field(default_factory=ToolPermissions)
    edit: ToolPermissions = Field(default_factory=ToolPermissions)
    bash: ToolPermissions = Field(default_factory=ToolPermissions)
    run_tests: ToolPermissions = Field(default_factory=ToolPermissions)
    repl: ToolPermissions = Field(default_factory=ToolPermissions)
    list_background_processes: ToolPermissions = Field(default_factory=ToolPermissions)
    read_background_output: ToolPermissions = Field(default_factory=ToolPermissions)
    save_memory: ToolPermissions = Field(default_factory=ToolPermissions)
    fetch_webpage: ToolPermissions = Field(default_factory=ToolPermissions)
    agents: ToolPermissions = Field(default_factory=ToolPermissions)
    activate_skill: ToolPermissions = Field(default_factory=ToolPermissions)

    allowlist: list[str] = Field(default_factory=lambda: ["*.md", "*.txt", "*.py", "*.js", "*.ts", "*.json", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini"])
    denylist: list[str] = Field(default_factory=lambda: ["/etc/passwd", "/etc/shadow", "/etc/hosts", "~/.ssh/*", "~/.aws/*", "~/.kube/*", "*.key", "*.pem", "*.p12", "*.pfx"])
    sensitive_patterns: list[str] = Field(default_factory=lambda: ["*secret*", "*password*", "*credential*", "*token*", "*api_key*", "*private_key*", "*.env", "*.env.*", "config/production*", "config/prod*"])
    connectors: list[Any] = Field(default_factory=list)


class AsyncSettings(BaseModel):
    max_concurrent_agents: int = 5
    max_concurrent_tools: int = 10
    default_timeout: int = 1800  # 30 minutes default for LLM operations
    enable_background_tasks: bool = True
    resource_monitoring: bool = True
    progress_updates: bool = True


class JarvisSettings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    async_settings: AsyncSettings = Field(default_factory=AsyncSettings, alias="async")
    heartbeat: HeartbeatSettings = Field(default_factory=HeartbeatSettings)
    learning: LearningSettings = Field(default_factory=LearningSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    theme: str = "dark"
    keybindings: str = "default"

    # Extension-specific configuration (free-form dict)
    extensions: dict[str, Any] = Field(default_factory=dict)

    bypass_tool_permissions: bool = False
    disallowed_tools: list[str] = Field(default_factory=list)
    agent_paths: list[str] = Field(default_factory=list)
    enabled_agents: list[str] = Field(default_factory=list)
    disabled_agents: list[str] = Field(default_factory=list)
    vibe_code_enabled: bool = False
