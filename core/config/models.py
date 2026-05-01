from typing import Any
from pydantic import BaseModel, Field

class AppSettings(BaseModel):
    name: str = "JARVIS"
    version: str = "2.0.1"
    debug: bool = False
    installed_agents: list[str] = Field(default_factory=list)

class ProviderSettings(BaseModel):
    config_file: str = "providers.json"
    selected_provider_id: str | None = None

class MemorySettings(BaseModel):
    max_entries: int = 1000
    importance_threshold: float = 0.5
    max_conversation_history: int = 50

class RagSettings(BaseModel):
    enabled: bool = True
    max_results: int = 5
    similarity_threshold: float = 0.7

class SafetySettings(BaseModel):
    require_confirmation: bool = True
    auto_checkpoint: bool = True
    max_checkpoints: int = 10

class ToolPermissions(BaseModel):
    permission: str = "ask"

class ToolSettings(BaseModel):
    enable_code_execution: bool = True
    enable_file_operations: bool = True
    enable_git_operations: bool = True
    
    # Tool permissions
    read: ToolPermissions = Field(default_factory=lambda: ToolPermissions(permission="always"))
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
    invoke_agent: ToolPermissions = Field(default_factory=ToolPermissions)
    activate_skill: ToolPermissions = Field(default_factory=ToolPermissions)
    
    allowlist: list[str] = Field(default_factory=lambda: ["*.md", "*.txt", "*.py", "*.js", "*.ts", "*.json", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini"])
    denylist: list[str] = Field(default_factory=lambda: ["/etc/passwd", "/etc/shadow", "/etc/hosts", "~/.ssh/*", "~/.aws/*", "~/.kube/*", "*.key", "*.pem", "*.p12", "*.pfx"])
    sensitive_patterns: list[str] = Field(default_factory=lambda: ["*secret*", "*password*", "*credential*", "*token*", "*api_key*", "*private_key*", "*.env", "*.env.*", "config/production*", "config/prod*"])
    connectors: list[Any] = Field(default_factory=list)

class InterfaceSettings(BaseModel):
    cli_prompt: str = "JARVIS > "
    vibe_code_enabled: bool = False

class AsyncSettings(BaseModel):
    max_concurrent_agents: int = 5
    max_concurrent_tools: int = 10
    default_timeout: int = 30
    enable_background_tasks: bool = True
    resource_monitoring: bool = True
    progress_updates: bool = True

class JarvisSettings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    rag: RagSettings = Field(default_factory=RagSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    interface: InterfaceSettings = Field(default_factory=InterfaceSettings)
    async_settings: AsyncSettings = Field(default_factory=AsyncSettings, alias="async")
    
    bypass_tool_permissions: bool = False
    agent_paths: list[str] = Field(default_factory=list)
    enabled_agents: list[str] = Field(default_factory=list)
    disabled_agents: list[str] = Field(default_factory=list)
