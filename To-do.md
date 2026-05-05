# JARVIS v2.0 Development Todo List

## ✅ Already Implemented

### Core Architecture
- [x] Base agent architecture with tool calling loop
- [x] CodingAgent for general tasks
- [x] ExploreAgent for codebase exploration
- [x] PlanAgent for task decomposition
- [x] ToolRegistry for tool management

### Tools (14+ tools available)
- [x] File operations (read, write, edit, glob, grep)
- [x] Code execution (bash, repl)
- [x] Web fetching
- [x] Memory management
- [x] Agent invocation
- [x] Skill management
- [x] Background process management

### Interfaces
- [x] CLI interface with argument parsing
- [x] TUI interface (Textual-based)
- [x] Web UI (basic structure)

### Configuration
- [x] Settings system with TOML config
- [x] Permission system with 5 safety profiles
- [x] Multi-LLM provider support (OpenAI, Anthropic)
- [x] .env file support

## 🚧 In Progress / Needs Attention

### Documentation
- [ ] Add uv venv setup instructions to README
- [ ] Document that CLI is still in development
- [ ] Update quickstart to clarify `jarvis --tui` uses env defaults
- [ ] Add comprehensive API documentation

### Testing
- [ ] Add tests for new tools (skill_manage_tool, permission_manager)
- [ ] Add integration tests for TUI
- [ ] Add tests for async agent functionality
- [ ] Test all 5 safety profiles

### Bug Fixes & Improvements
- [ ] Fix duplicate `registry.py` files (core/tools/registry.py vs core/tools/async_registry.py)
- [ ] Review and consolidate permission system
- [ ] Ensure all tools properly handle streaming callbacks
- [ ] Fix any type checking issues (`ty check .`)

## 📋 TODO: Core Development Tasks

### Agent System
- [ ] Implement agent streaming response handling
- [ ] Add agent-to-agent communication patterns
- [ ] Implement agent state persistence
- [ ] Add agent checkpointing and recovery

### Tool System
- [ ] Add tool result formatting for TUI/CLI/web display
- [ ] Implement tool result caching
- [ ] Add tool execution timeouts and cancellation
- [ ] Implement concurrent tool execution (max_concurrent_tools)
- [ ] Add tool usage analytics

### Memory System
- [ ] Implement vector-based RAG (enabled in config but needs work)
- [ ] Add memory importance scoring
- [ ] Implement memory consolidation
- [ ] Add memory export/import functionality

### Learning System
- [ ] Enable learning loop (currently disabled)
- [ ] Implement skill auto-creation from tool patterns
- [ ] Add self-evaluation checkpoints
- [ ] Implement skill prompting for LLM

### Safety & Permissions
- [ ] Implement 5 safety profiles in TUI (NEUTRAL, SAFE, DESTRUCTIVE, YOLO, EXPLORE)
- [ ] Add file path permission overrides
- [ ] Implement sensitive file detection
- [ ] Add approval workflow for denied tools

### Interfaces
- [ ] Complete TUI agent loop integration
- [ ] Add TUI keybindings for safety profiles (Shift+Tab)
- [ ] Implement TUI streaming display
- [ ] Add web UI agent interaction
- [ ] Implement websocket handling for tool results

### Configuration
- [ ] Add config.toml example file
- [ ] Implement provider configuration UI
- [ ] Add model selection per-session
- [ ] Implement configuration migration

## 🔧 Technical Debt

- [ ] Remove duplicate registry files
- [ ] Consolidate permissions.py across modules
- [ ] Standardize callback type definitions
- [ ] Clean up unused imports
- [ ] Add missing type hints

## 📦 Release Checklist (v2.0.0)

- [ ] All tests passing
- [ ] Type checking clean (`ty check .`)
- [ ] Documentation complete
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `jarvis/_version.py`
- [ ] README badge updates
- [ ] PyPI package ready

## 🎯 Future Features (Post v2.0)

- [ ] Plugin system for custom tools
- [ ] Remote agent connections
- [ ] Voice interface
- [ ] Mobile companion app
- [ ] IDE extensions (VSCode, JetBrains)
- [ ] GitHub integration (PRs, issues)
- [ ] Slack/Discord integration