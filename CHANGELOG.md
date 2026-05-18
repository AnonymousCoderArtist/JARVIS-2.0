# JARVIS Changes & Improvements

## Overview

This document summarizes all the fixes, improvements, and UI updates made to the JARVIS project during the current development session.

---

## Unreleased

### Agent Loop Stability
- **Max turns from env** — `JARVIS_MAX_TURNS` (default: 100) and `JARVIS_MAX_CONSECUTIVE_SKIPS` (default: 5) configurable via `.env`
- **Infinite loop prevention** — Agent loop stops after max turns or consecutive skipped tool calls
- **Required args validation** — Tools validate required arguments before permission checks, preventing empty tool calls
- **Empty args handling** — Empty string arguments parsed correctly instead of causing JSON decode errors

### Tool System Fixes
- **Approval widget crash** — Empty dicts skip pydantic validation in `get_approval_widget()`, preventing `BashArgs` ValidationError
- **read_memory tool** — Fixed `None` default values causing `'>=' not supported between instances of 'int' and 'NoneType'` error
- **Memory directory creation** — `get_scope_dir()` now creates `private`/`team` directories automatically if they don't exist
- **Cross-platform shell detection** — `BashTool` uses `shutil.which("bash")` instead of hardcoded `/bin/bash` for Linux distro compatibility

### TUI/Approval Flow
- **ApprovalApp type flexibility** — Accepts both `BaseModel` and `dict` for `tool_args`
- **Approval callback** — Properly converts `BaseModel` to dict before passing to approval widget

### Updated knowledge graph (graphify) for v2.1 codebase state

## v2.1.0 — Extension System, Event/Hook Architecture, Persistent Memory & RPC Mode

### Extension System (New)

A full plugin architecture for extending JARVIS with custom tools, hooks, commands, and shortcuts.

- **ExtensionAPI** — Public surface exposed to every extension (`register_tool`, `register_command`, `on`, `register_hook`, `register_shortcut`)
- **ExtensionLoader** — Dynamic discovery from `.jarvis/extensions/*.py`, `~/.jarvis/extensions/*.py`, and pip entry points
- **ExtensionRunner** — Full lifecycle: discover → load → bind → run → unbind
- **ExtensionRegistry** — Metadata tracking, conflict detection, tool origin lookup
- **Tool override** — Extensions can replace built-in tools with conflict logging
- **Example extensions** in `examples/extensions/`: hello_world, audit_tool, safety_gate, event_logger, ssh_operations

**Files Added:**
- `core/extensions/__init__.py`, `api.py`, `loader.py`, `runner.py`, `registry.py`, `types.py`
- `examples/extensions/hello_world.py`, `audit_tool.py`, `safety_gate.py`, `event_logger.py`, `ssh_operations.py`, `ssh_tools.py`

### Event & Hook System (New)

Dual-layer event-driven architecture for observability and lifecycle interception.

- **EventBus** (`core/events/bus.py`) — Per-session pub/sub with priority ordering, polymorphic dispatch (MRO walking), introspection stats
- **HookRegistry** (`core/events/hooks.py`) — 16 lifecycle stages (`BEFORE_TOOL_CALL`, `AFTER_TURN`, etc.), handlers can block/modify/inject
- **24 event types** across 8 categories: Agent, Turn, Message, Tool, Session, Extension, Status, System
- `HookContext` — Rich context object passed to handlers (agent state, tool args, messages, etc.)
- `HookResult` — Control execution: `proceed`, `block`, `modify`, `inject`

**Files Added:**
- `core/events/__init__.py`, `bus.py`, `hooks.py`, `types.py`

### Pluggable Operations Backend (New)

Decouples tool implementations from OS calls via `OperationsRegistry`.

- **FileOperations protocol** — `read_file`, `write_file`, `list_dir`, `glob`
- **BashOperations protocol** — `run_command`
- **EditOperations protocol** — `edit_file`
- **Default local implementations** via `aiofiles`/`asyncio`
- Extensions can swap backends: `api.operations_registry.set_bash_ops(ssh_backend)`

**Files Added:**
- `core/tools/operations/__init__.py`, `base.py`, `local.py`, `registry.py`

### Persistent Memory System (New)

Structured, typed, scoped memory inspired by OpenClaude and Hermes.

- **6 memory types**: user, feedback, project, project_context, reference, global
- **3 scopes**: private (`.jarvis/memory/private/`), team, global (`~/.jarvis/global_memory/`)
- **Rich metadata**: YAML frontmatter (name, description, type, scope, priority, tags, project)
- **Auto-indexing**: `MEMORY.md` index files per scope
- **Advanced search**: Filter by type, scope, tags, priority, project, content query
- **Memory tools**: `save_memory` (structured), `read_memory` (searchable), `memory` (Hermes-style MEMORY.md/USER.md)
- **Security scanning**: Sensitive pattern detection before saving
- **Character limits**: MEMORY.md (2200 chars), USER.md (1375 chars)

**Files Added:**
- `core/tools/memory_tool.py`

### RPC Mode (New)

JSONL protocol over stdin/stdout for embedding JARVIS in IDEs, web UIs, or other processes.

- **10 commands**: prompt, steer, follow_up, bash, compact, new_session, get_state, get_messages, get_tools, set_model
- **Streaming events**: text_delta, thinking_delta, tool_call_start/end, turn_start/end, status, session_started
- Full agent session lifecycle in a single process
- Launched via `jarvis --mode rpc`

**Files Added:**
- `core/rpc/__init__.py`, `handler.py`, `types.py`

### Prompt Template System (New)

Markdown files with YAML frontmatter auto-register as slash commands.

- Frontmatter: `name`, `description`, `arguments` (comma-separated)
- Shell-style argument substitution: `$1`, `$2`, `$@`, `${@:2}`, `${@:N}`
- Discovered from `.jarvis/prompts/` and `~/.jarvis/prompts/` (tiered discovery)
- Example templates in `examples/prompts/`: review, testgen, explain

**Files Added:**
- `core/prompts/__init__.py`, `templates.py`
- `examples/prompts/review.md`, `testgen.md`, `explain.md`

### Resource Discovery (New)

Tiered resource discovery for config, prompts, skills, and system files.

- Scans `~/.jarvis/`, `.jarvis/`, and walks up from cwd (precedence: project > user > global)
- Discovers `AGENTS.md`, `CLAUDE.md`, `SYSTEM.md`, skills, prompt templates
- `core/resources/__init__.py`, `loader.py`

### Theme & Keybinding Systems (New)

- **Theme system**: 51 color tokens (backgrounds, text, accents, borders, status), truecolor/256 detection, hot-reload
- **Keybinding system**: Namespaced action IDs (`app.send`, `edit.cancel`, `panel.toggle`), legacy migration, JSON config
- `core/config/theme.py`, `core/config/keybindings.py`

### Rewind System (Improved)

- File snapshots before each user message
- Checkpoint-based message truncation
- Session forking for parallel exploration

### Agent Activity Tracking (New)

- `SubagentActivity` — view-only activity events for subagents (info, tool_use, tool_result, output)
- `AgentMemorySnapshot` — memory snapshots for fork isolation and persistence
- Thread-safe async operations

### New Agent: Rubber Duck Agent

- Constructive critique and code review specialist
- `core/agents/builtin/rubber_duck_agent.py`

### New Tools

- **ToolSearchTool** — Keyword search over tool names, descriptions, and search hints
- **MemoryManagementTool** — Hermes-style `memory` tool for MEMORY.md/USER.md management
- **EnterWorktreeTool / ExitWorktreeTool** — Git worktree management
- **MCPProxyTool** — Unified MCP proxy tool with metadata cache and lifecycle management

### MCP Improvements

- Lazy connection architecture — servers connect only when tools are called
- `MCPMetadataCache` — offline metadata cache at `~/.jarvis/mcp-cache.json`
- `MCPLifecycleManager` — lazy/eager/keep-alive connection modes
- `MCPProxyTool` — single proxy tool (status/list/search/describe/call/connect)
- Authentication support: OAuth2, Bearer tokens, API keys
- Resource and prompt template support

### Learning System Improvements

- ML-based interaction classification (`core/learn/Classification/`)
- `TraceAnalyzer` for deeper interaction analysis
- Configurable training data management

### WebUI Enhancements

- Context usage fix (attribute name `agent.provider` → `agent.llm`)
- Context progress bar with color-coded thresholds
- Inline tool calls in chat panel
- Design token system (CSS variables + 25 reusable component classes)
- Enter sends, Shift+Enter newline
- Active tool call widget
- Dot grid color & modulo fix
- Model picker, MCP panel, heartbeat monitor, rewind dialog
- Config panel, voice input, feedback widget, debug console
- Question dialog, approval dialog
- Slash commands panel navigation

### Platform Compatibility

- Conditional Windows imports (`sys.platform == "win32"`)
- Python 3.11 compatibility (TypeVar + Generic, no f-string backslashes)
- Cross-platform path handling

### System Prompt Optimization

- Rewritten in Markdown + XML hybrid format
- ~15% token reduction (4,872 → 4,125 tokens)
- 16 sharp directives replacing verbose bullet points
- XML `<constraints>`, `<editing-rules>`, `<security-rules>` per agent

### Files Modified

| File | What Changed |
|------|-------------|
| `core/agents/jarvis_v2.py` | Hook integration, memory injection, event emission |
| `core/agents/base.py` | EventBus wiring, hook execution in agent loop |
| `core/tools/registry.py` | OperationsRegistry integration, lazy imports |
| `core/web/server.py` | 14 new API endpoints, context usage fix, accumulated tracking |
| `core/config/settings.py` | Extension settings, theme, keybinding support |
| `core/config/models.py` | New config models for extensions, operations |
| `core/agents/prompts/` | Token-optimized system prompts |
| `core/agents/system_prompts.py` | 16 rule directives, memory-first instruction |
| `interface/textual_ui/` | TUI visual overhaul, color palette theming |
| `interface/webui/src/` | Design tokens, layout fixes, 10+ new panels |
| `interface/cli/cli.py` | Conditional Windows imports |
| `pyproject.toml` | Updated dependencies, version 2.1.0 |

### Files Added

| File | Purpose |
|------|---------|
| `core/events/` | EventBus + HookRegistry + 24 event types |
| `core/extensions/` | Extension API, loader, runner, registry |
| `core/tools/operations/` | Pluggable file/bash/edit backends |
| `core/tools/memory_tool.py` | Structured persistent memory system |
| `core/rpc/` | JSONL RPC protocol for IDE/process embedding |
| `core/prompts/` | Prompt template system (markdown → slash commands) |
| `core/resources/` | Tiered resource discovery |
| `core/config/theme.py` | 51-token theme system |
| `core/config/keybindings.py` | Namespaced keybinding system |
| `core/agents/builtin/rubber_duck_agent.py` | Code review specialist agent |
| `core/tools/tool_search_tool.py` | Tool discovery and search |
| `core/tools/worktree_tool.py` | Git worktree management |
| `core/tools/mcp_proxy_tool.py` | Unified MCP proxy tool |
| `core/tools/mcp_lifecycle.py` | MCP connection lifecycle management |
| `core/tools/mcp_metadata_cache.py` | Offline MCP metadata caching |
| `core/tools/mcp_capabilities.py` | MCP server capabilities tracking |
| `core/tools/mcp_auth.py` | MCP authentication support |
| `core/tools/agent/agent_memory.py` | Agent activity tracking + snapshots |
| `examples/extensions/` | Reference extension examples |
| `examples/prompts/` | Prompt template examples |

---

## Context Usage Fix & WebUI Layout Improvements

### Problem
The `/api/context/usage` REST endpoint always returned zero tokens because it checked `hasattr(agent, 'provider')` but the agent stores its LLM provider as `self.llm`. The WebUI `ContextUsageBar` component polled this endpoint but showed 0% at all times.

Additionally, the WebUI input had nested `fixed` positioning (ChatInput wrapped in a fixed container inside another fixed container), causing incorrect layout behavior.

### Backend Fix
- **Fixed attribute name**: `agent.provider` → `agent.llm` in `/api/context/usage` endpoint
- **Added cumulative token accumulation**: After each `agent.process(content)` completes in the WebSocket handler, token usage is read via `agent.llm.get_and_clear_usage()` and accumulated into a module-level `_accumulated_usage` dict (mirrors the TUI's `Stats.update_from_agent()` pattern)
- **REST endpoint returns accumulated data**: Uses `_accumulated_usage` by default, falls back to live `get_and_clear_usage()` if no accumulated data yet

### WebUI Frontend
- **New `ContextUsageBar.tsx`**: Always-visible inline context usage indicator in the bottom bar, polls every 5s, color-coded progress bar (green <70%, yellow 70-80%, orange 80-90%, red >90%) matching the TUI pattern
- **Fixed ChatInput layout**: Removed nested `fixed` positioning wrapper — ChatInput now uses `relative` positioning, parent container handles the fixed placement
- **Inline tool calls in ChatPanel**: Tool calls from the last assistant message render directly inside the chat panel (spinner for pending, checkmark for success, X for error)
- **ToolCallBox repositioned**: Initial position moved from far-right (`window.innerWidth - 340`) to directly next to ChatPanel (`window.innerWidth / 2 + 260`)

### Files Changed
| File | Change |
|------|--------|
| `core/web/server.py` | Fixed `agent.provider` → `agent.llm`, added `_accumulated_usage` + accumulation after turn end |
| `interface/webui/src/components/techy/ContextUsageBar.tsx` | **New** — inline always-visible context usage bar with color-coded progress |
| `interface/webui/src/components/techy/ChatInput.tsx` | Fixed nested `fixed` positioning → `relative` |
| `interface/webui/src/components/techy/ChatPanel.tsx` | Added `ToolCallsInline` component showing tool calls inside chat panel |
| `interface/webui/src/components/techy/TechShell.tsx` | Added `ContextUsageBar` import, repositioned ToolCallBox, restructured bottom bar |

### Files Added
- `interface/webui/src/components/techy/ContextUsageBar.tsx`

---

## System Prompt Optimization (Token-Efficient)

### Problem
System prompts across all agents used verbose narrative paragraphs, consuming excessive tokens (~4,872 total) while providing no structural advantage for model comprehension.

### Solution
Rewrote all prompts using **Markdown + XML hybrid format**: Markdown for readable structure (headings, lists, tables), XML tags for critical constraints that must not be ignored. Removed narrative fluff, combined behaviors into single directives.

### Token Reduction

| Prompt | Role | Before → After | Reduction |
|--------|------|----------------|-----------|
| `explore.py` | 🔍 Codebase Analysis | 525 → 480 tokens | -9% |
| `plan.py` | 📋 Architecture Planning | 800 → 695 tokens | -13% |
| `verification.py` | ✅ Testing Specialist | 700 → 667 tokens | -5% |
| `jarvis_v2.py` | 🤖 Main Agent | 2,287 → 1,879 tokens | -18% |
| `__init__.py` General Purpose | ⚡ Multi-step Tasks | 120 → 88 tokens | -27% |
| `__init__.py` Fork | 🍴 Parallel Execution | 130 → 90 tokens | -31% |
| `__init__.py` JARVIS Help | ❓ Help Agent | 170 → 130 tokens | -24% |
| `__init__.py` Statusline | 💻 Shell Specialist | 140 → 96 tokens | -31% |

**Total: ~4,872 → ~4,125 tokens (15% reduction)**

### Files Changed
- `core/agents/prompts/explore.py` — XML `<constraints>` for read-only, dense directive lists
- `core/agents/prompts/plan.py` — XML `<constraints>`, condensed plan format + examples
- `core/agents/prompts/verification.py` — XML `<personality>`, compressed methodology
- `core/agents/prompts/jarvis_v2.py` — XML `<editing-rules>`, `<output-rules>`, `<task-rules>`, `<security-rules>`, `<safety-rules>`, `<response-rules>`
- `core/agents/prompts/__init__.py` — Inline prompts for general-purpose, fork, help, statusline

---

## WebUI: Thinking Level Picker Removed

### Problem
The thinking level selector (Low/Medium/High) was unused — reasoning is controlled at the model/provider level, not the UI level.

### Solution
Removed the `ThinkingPicker` component and all associated `thinking_level` plumbing from the frontend.

### What Changed
- Removed `ThinkingPicker` from `ChatInput.tsx` — no more dropdown in the input bar
- Removed "Thinking Level" section from `ConfigPanel.tsx`
- Removed `thinkingLevel` parameter from `send()`, `handleSend()`, `client.sendMessage()`
- Removed `thinking_level` from `SettingsPayload`, `SettingsUpdate`, `Outbound` types
- Removed `thinking_level` query param from `updateSettings` API call

### Kept Intact
ThinkingIndicator, ThinkingBlock, reasoning display, SphereResponse, `thinking` state, `reasoning`/`reasoning_end` WebSocket events — all reasoning *display* functionality remains.

### Files Changed
- `interface/webui/src/components/techy/ChatInput.tsx`
- `interface/webui/src/components/techy/TechShell.tsx`
- `interface/webui/src/components/techy/ConfigPanel.tsx`
- `interface/webui/src/hooks/useJarvisStream.ts`
- `interface/webui/src/lib/jarvis-client.ts`
- `interface/webui/src/lib/types.ts`
- `interface/webui/src/lib/api.ts`

---

## WebUI: Enter Sends, Shift+Enter Newline

### Problem
Pressing Enter in the chat input did not send the message — users had to click the send button.

### Solution
Added `Enter` → send, `Shift+Enter` → newline behavior (standard LLM UI pattern).

### Files Changed
- `interface/webui/src/components/techy/ChatInput.tsx` — `onKeyDown` handler sends on Enter (no Shift), preserves newline on Shift+Enter

---

## WebUI: Active Tool Call Widget

### Problem
No visible indication of what tools the LLM was actively calling during streaming.

### Solution
Added `ToolCallWidget` — a compact pill widget that appears above the chat input bar showing running tool names with animated status dots. Auto-hides when all tools complete or streaming stops.

### Files Added
- `interface/webui/src/components/techy/ToolCallWidget.tsx`

### Files Modified
- `interface/webui/src/components/techy/TechShell.tsx` — imports and renders `ToolCallWidget`

---

## WebUI: Dot Grid Color Changed

### Problem
Dot grid dots were brand blue (`rgba(var(--brand-r), ...)`), making them blend with the background on dark themes.

### Solution
Changed dot color to white (`rgba(255, 255, 255, 0.25)`) for better visibility.

### Files Changed
- `interface/webui/src/components/techy/DotGrid.tsx` — line 50

---

## OpenAI SDK: `reasoning_content` AttributeError Fix

### Problem
`'ChoiceDelta' object has no attribute 'reasoning_content'` — the OpenAI SDK's `ChoiceDelta` doesn't expose `reasoning_content` on all models (only DeepSeek-compatible ones). Direct attribute access crashed streaming with tools.

### Solution
Changed `delta.reasoning_content` to `getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)` — safe fallback for models without reasoning support.

### Files Changed
- `core/llm_sdk/openai/sdk.py` — line 38

---

## WebUI Design Token Refactoring

### Problem
The WebUI had ~400+ hardcoded `rgba()` color values spread across 30 component files. Changing the theme required editing every file individually — colors like `rgba(26, 90, 255, ...)` and `rgba(200, 220, 255, ...)` were duplicated everywhere with no single source of truth.

### Solution
Introduced a centralized **design token system** using CSS custom properties (RGB channel variables) in `globals.css`, and **reusable component CSS classes** for common UI patterns.

### What Changed

**1. Design Tokens in `globals.css`**
- Added RGB channel CSS variables in `:root`:
  - `--brand-r/g/b` — primary accent blue (was 26, 90, 255)
  - `--text-bright-r/g/b` — headings/titles (was 200, 220, 255)
  - `--text-body-r/g/b` — body text (was 180, 200, 230)
  - `--text-muted-r/g/b` — labels/secondary (was 100, 140, 220)
  - `--success-r/g/b`, `--error-r/g/b`, `--warning-r/g/b` — status colors
  - `--dialog-bg-start/end-r/g/b` — panel gradient colors

**2. 25 Reusable CSS Component Classes**
- `.techy-panel`, `.techy-dialog`, `.techy-dialog-amber`, `.techy-dialog-debug`
- `.techy-header`, `.techy-header-amber`, `.techy-header-debug`
- `.techy-btn-active`, `.techy-btn-selected`, `.techy-btn-active-amber`
- `.techy-topmenu`, `.techy-input-bar`, `.techy-suggestions`, `.techy-connection-bar`
- `.techy-bubble-user`, `.techy-bubble-assistant`, `.techy-bubble-reasoning`
- `.techy-text-title`, `.techy-text-body`, `.techy-text-muted`, `.techy-text-dim`
- `.techy-badge-question`, `.techy-badge-approval`
- `.techy-sphere-response`, `.techy-feedback`, `.techy-right-sidebar`, `.techy-sidebar-btn`

**3. 29 Component Files Refactored**
Every hardcoded `rgba()` and hex color replaced with CSS variable references. Common inline style blocks replaced with `.techy-*` CSS classes.

### How to Theme
Change RGB values in ONE file (`src/globals.css` `:root`) — everything cascades.

### Files Changed
- `interface/webui/src/globals.css` — Design tokens + 25 reusable component classes
- `interface/webui/src/App.tsx` — Loading/error state colors
- `interface/webui/src/components/MarkdownTextRenderer.tsx` — All markdown element colors
- `interface/webui/src/components/CodeBlock.tsx` — Syntax highlighting UI colors
- `interface/webui/src/components/ConnectionBadge.tsx` — Status badge colors
- `interface/webui/src/components/thread/ToolCallBlock.tsx` — Tool call status colors
- `interface/webui/src/components/techy/` (25 files) — All panel, dialog, and component colors

---

## Platform Compatibility Fixes

### Windows vs Linux Conditional Imports

**Problem:** On Linux, importing `pywintypes` and Windows-specific tools caused `ModuleNotFoundError`.

**Solution:** Made all Windows tool imports and registrations conditional on `sys.platform == "win32"`.

**Files changed:**
- `core/tools/__init__.py` — Conditional Windows tool imports and `__all__` extension
- `interface/textual_ui/tui_main.py` — Conditional Windows tool registration in `_build_tool_registry`
- `interface/cli/cli.py` — Conditional Windows tool registration in `_initialize_tools`

### Python 3.11 Compatibility

**Problem:** Python 3.12 class type parameter syntax (`class Foo[T: BaseModel]`) was incompatible with Python 3.11.

**Solution:** Converted to pre-3.12 `TypeVar` + `Generic[T]` syntax.

**File changed:**
- `interface/textual_ui/widgets/tool_widgets.py` — `ToolApprovalWidget` and `ToolResultWidget` generics

### F-String Backslash Syntax

**Problem:** F-string expressions containing backslash escapes are invalid in Python <3.12.

**Solution:** Moved `.replace("\\", "/")` calls outside of f-string expressions.

**File changed:**
- `interface/textual_ui/cli_adapters.py` — Two path display lines (lines 1776 and 1797)

---

## Tool System Fixes

### Edit Tool Widget Mapping Bug

**Problem:** The `edit` tool was incorrectly mapped to `WriteFileArgs` in `ARGS_MODELS` and `WriteFileApprovalWidget`/`WriteFileResultWidget` in the widget registries. Since `edit` uses a `replacements` array (not `file_path`/`content`), this caused a `ValidationError` when the tool was called.

**Solution:**
- Removed `"edit"` from `ARGS_MODELS` mapping so it falls back to generic dict handling
- Removed `"edit"` from `APPROVAL_WIDGETS` and `RESULT_WIDGETS` so it uses base generic widgets
- Separated `edit` display logic in `cli_adapters.py` to extract `filePath` from the first replacement in the array

**Files changed:**
- `interface/textual_ui/widgets/tool_widgets.py` — Removed `edit` from widget and args registries
- `interface/textual_ui/cli_adapters.py` — Split `edit` display handling from `write`/`write_file`

### WriteFileApprovalWidget Crash

**Problem:** `WriteFileApprovalWidget` accessed `self.args.filePath`, but `WriteFileArgs` defines the field as `file_path` (snake_case). This caused `AttributeError` on every write approval.

**Solution:** Changed to `self.args.file_path` with a fallback to `self.args.get("file_path", self.args.get("filePath", ""))` for dict inputs.

**File changed:**
- `interface/textual_ui/widgets/tool_widgets.py` — `WriteFileApprovalWidget.compose`

---

## System Prompt Improvements

**File changed:** `core/agents/system_prompts.py`

### What Changed
- **Read tool instructions** — Now explicitly requires `offset` and `limit` usage (no full-file reads)
- **Header** — More concise and directive: "Be direct, concise, and action-oriented. Never show your reasoning process."

### New Behavior Rules
Replaced ~30 verbose bullet points with 16 sharp, numbered directives:

| Rule | Summary |
|------|---------|
| 1 | Be agentic — act, don't just describe |
| 2 | Read before you edit |
| 3 | Use `edit` for surgical changes, `write` only for new/replace |
| 4 | Be concise, no preamble or meta-commentary |
| 5 | Run tests after changes |
| 6 | Explain shell commands before running |
| 7 | Don't expose secrets |
| 8 | Admit when you don't know |
| 9 | Do meaningful work before checking subagent status |
| 10 | **DO NOT re-read files to verify edits** |
| 11 | **MAXIMUM 2 reads per file per task** |
| 12 | **DO NOT run the same check repeatedly** |
| 13 | **If an edit succeeds, check once and move on** |
| 14 | **Short acknowledgments only** ("good job" → "Thanks", stop) |
| 15 | **Remember task state** — brief feedback = acknowledgment, not a new task |
| 16 | **Memory first** — read memories at session start |

---

## TUI Visual Overhaul

### Design System

A cohesive dark theme with a new color palette:

| Variable | Color | Usage |
|----------|-------|-------|
| `$surface` | `#1a1a2e` | Deep navy background |
| `$surface-light` | `#16213e` | Panels, cards, popups |
| `$text-primary` | `#e0e0e0` | Main text |
| `$text-secondary` | `#8b8b9a` | Muted/hint text |
| `$accent` | `#FF8205` | Brand orange, headings, user messages |
| `$success` | `#4ade80` | Success states, tool results |
| `$warning` | `#facc15` | Warnings, approval dialogs |
| `$error` | `#f87171` | Errors, failed tool results |
| `$info` | `#60a5fa` | Info, tool calls, directories |
| `$border-subtle` | `#2a2a3e` | Borders, dividers |

### Changes in `app.tcss`

- **Screen background** — `$surface` (was transparent)
- **Chat area** — Padded for breathing room
- **Input box** — `$surface-light` background with `$border-subtle` border; colored borders for warning/safe/error/recording states
- **User messages** — Orange left border (`$accent`) + subtle background tint
- **Assistant messages** — Subtle left border for visual hierarchy
- **Code blocks** (`MarkdownFence`) — `$surface-light` background with border, proper padding
- **Blockquotes** — Orange left border + background
- **Tool calls** — Blue (`$info`) left border + background tint
- **Tool results** — Green (`$success`) left border + background; red for errors, yellow for warnings
- **Loading widget** — Orange left border + background
- **Banner** — Orange brand with subtle background padding
- **Approval popup** — Yellow (`$warning`) border to stand out as "needs attention"
- **Config/question popups** — `$surface-light` background instead of transparent
- **Markdown headings** — Orange accent color
- **Scrollbars** — Themed to match palette

### Changes in `tools.tcss`

- **Tool result summaries** — Blue info color, hover effects with background
- **Bash commands** — Green text with background highlight
- **Grep matches** — Subtle background for readability
- **LS directories** — Cyan bold; files in primary text
- **Todos** — Consistent green/yellow/secondary colors
- All `ansi_*` references replaced with palette variables

---

## WebUI: Context, Connector Auth, Safety Profiles

### Context Progress (Token Usage)
- New `ContextProgress.tsx` panel showing real-time token usage with progress bars
- Displays context window utilization + output budget as animated bars
- Input/Output/Total token counts with live 3s auto-refresh
- Backend: `GET /api/context/usage` — reads `SDKAdapter.get_and_clear_usage()` + `ContextLengthManager`

### Connector Auth UI
- New `ConnectorAuth.tsx` panel listing all 5 connectors (GitHub, HTTP, RSS, OpenWeatherMap, Filesystem)
- Connection status indicators (green/offline), expandable credential forms per connector
- GitHub: token + username; Weather: API key + city; generic token input for others
- Credentials saved to `~/.jarvis/credentials/` via `ConnectorRegistry`
- Backend: `GET /api/connectors` + `POST /api/connectors/{name}/auth`

### Safety Profiles (Shift+Tab)
- New `SafetyProfile.tsx` with 5 levels: Lockdown → Restricted → Balanced → Permissive → Unrestricted
- Visual icons per level (red shield → purple zap), live checkmark on active
- **Shift+Tab keyboard shortcut** cycles profiles globally (wraps 1→2→3→4→5→1)
- Backend: `GET /api/safety/profile` + `POST /api/safety/profile` — sets `JARVIS_BYPASS_PERMISSIONS` and `JARVIS_CODE_PERMISSION`

### Files Added
- `interface/webui/src/components/techy/ContextProgress.tsx` — Token usage display
- `interface/webui/src/components/techy/ConnectorAuth.tsx` — Connector credential management
- `interface/webui/src/components/techy/SafetyProfile.tsx` — 5-level safety selector

### Files Modified
- `core/web/server.py` — Added 5 new endpoints (context/usage, connectors/*, safety/profile)
- `interface/webui/src/components/techy/TechShell.tsx` — Shift+Tab handler, 3 new panel states + sidebar icons
- `interface/webui/src/lib/types.ts` — Added ContextUsage, ConnectorInfo, SafetyProfile types
- `interface/webui/src/lib/api.ts` — Added getContextUsage, listConnectors, setConnectorAuth, get/setSafetyProfile

---

## WebUI Feature Expansion

### 10 New Feature Panels

All integrated into the existing techy-style UI (glass-morphism dark theme, draggable panels, blue accent palette):

| Feature | Component | Files |
|---------|-----------|-------|
| **Model Picker** | `ModelPicker.tsx` | Browse & switch LLM models grouped by provider, capability badges (reasoning/vision/tool_call) |
| **MCP Servers** | `McpPanel.tsx` | List/add/remove MCP servers, connection status indicators, transport type display |
| **Heartbeat Monitor** | `HeartbeatPanel.tsx` | Start/stop heartbeat scheduler, view file contents, last result display |
| **Rewind Dialog** | `RewindDialog.tsx` | Browse session checkpoints, rewind to any message, file change indicators |
| **Config/Settings** | `ConfigPanel.tsx` | Working preference toggles (code/file/git ops) with slide animation |
| **Voice Input** | `VoiceInput.tsx` | MediaRecorder API integration, recording state animation, sends blob to `/api/voice/transcribe` |
| **Feedback Widget** | `FeedbackWidget.tsx` | 3-emoji rating (good/ok/bad), optional detail message, persisted to `~/.jarvis/feedback.jsonl` |
| **Debug Console** | `DebugConsole.tsx` | Terminal-style command input, history with output display, available commands: ping/agent_status/health/clear_logs |
| **Question Dialog** | `QuestionDialog.tsx` | Renders `user_input` WebSocket events as structured forms with option buttons or free-text input |
| **Approval Dialog** | `ApprovalDialog.tsx` | Enhanced amber-themed tool approval overlay with always-allow toggle |

### TopMenu Redesign
- Added dropdown menu (click "JARVIS" label) listing all tool panels
- Quick-action buttons for Model Picker, MCP Servers, Settings
- Status indicator badges for pending questions and approval requests

### Slash Commands Expansion
- New commands open UI panels directly: `/model`, `/mcp`, `/heartbeat`(`/hb`), `/debug`(`/dbg`), `/feedback`(`/fb`)
- `/config` and `/rewind` now trigger their respective panels instead of sending text to AI
- All UI-triggering commands wired through ChatInput props to TechShell

### Backend API Endpoints Added (12 new)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/models` | List available models with capabilities |
| `GET /api/providers` | List configured LLM providers |
| `POST /api/settings/model` | Switch active model at runtime |
| `GET /api/mcp/servers` | List MCP server configs |
| `POST /api/mcp/servers` | Add a new MCP server |
| `DELETE /api/mcp/servers/{name}` | Remove an MCP server |
| `GET /api/heartbeat` | Heartbeat system status |
| `POST /api/heartbeat/start|stop` | Control heartbeat scheduler |
| `GET /api/sessions/{id}/checkpoints` | List rewind checkpoints |
| `POST /api/sessions/{id}/rewind` | Rewind to a checkpoint |
| `POST /api/voice/transcribe` | Voice transcription (placeholder) |
| `POST /api/feedback` | Submit feedback (persisted to JSONL) |
| `GET /api/debug/logs` | Get recent debug log entries |
| `POST /api/debug/command` | Execute debug command |

### WebSocket Question/Approval Flow
- `useJarvisStream` now handles `user_input` events, exposing `pendingQuestion` / `answerQuestion`
- `user_input` answers sent as regular messages back to agent
- `approval_request` events rendered through `ApprovalDialog` component

### DotGrid Canvas Fix
- Fixed negative modulo bug where `-N % 48` produced negative results, causing dots to shift incorrectly when panning with negative offsets
- Replaced with proper `mod(n, m) = ((n % m) + m) % m`
- Added `ResizeObserver` for reliable canvas sizing on layout changes
- Simplified draw loop to always render visible columns/rows without gap at edges

### Files Added
- `interface/webui/src/components/techy/ModelPicker.tsx` — Model browsing & selection
- `interface/webui/src/components/techy/McpPanel.tsx` — MCP server management
- `interface/webui/src/components/techy/HeartbeatPanel.tsx` — Heartbeat monitoring
- `interface/webui/src/components/techy/RewindDialog.tsx` — Session rewind UI
- `interface/webui/src/components/techy/ConfigPanel.tsx` — Settings & preferences
- `interface/webui/src/components/techy/VoiceInput.tsx` — Voice recording UI
- `interface/webui/src/components/techy/FeedbackWidget.tsx` — Feedback collection
- `interface/webui/src/components/techy/DebugConsole.tsx` — Developer debug console
- `interface/webui/src/components/techy/QuestionDialog.tsx` — Question form from WebSocket
- `interface/webui/src/components/techy/ApprovalDialog.tsx` — Tool approval overlay

### Files Modified
- `core/web/server.py` — 14 new API endpoints, model/MCP/heartbeat/rewind/voice/feedback/debug
- `interface/webui/src/components/techy/TechShell.tsx` — All panels wired with visibility state, question/approval integration
- `interface/webui/src/components/techy/TopMenu.tsx` — Dropdown menu, quick actions, status badges
- `interface/webui/src/components/techy/ChatInput.tsx` — VoiceInput integration, UI-triggering slash commands
- `interface/webui/src/components/techy/SlashCommands.tsx` — Added /model /heartbeat /debug /feedback commands
- `interface/webui/src/components/techy/DotGrid.tsx` — Proper modulo, ResizeObserver, reliable sizing
- `interface/webui/src/hooks/useJarvisStream.ts` — `user_input` event handling, `pendingQuestion`/`answerQuestion`
- `interface/webui/src/lib/types.ts` — Added types for ModelInfo, ProviderInfo, MCPServer, Heartbeat, Rewind, Voice, Feedback, Debug
- `interface/webui/src/lib/api.ts` — Added 15 new API methods for all new endpoints

---

## Files Modified

| File | What Changed |
|------|-------------|
| `core/agents/system_prompts.py` | Complete rewrite of guidelines (16 rules), updated header, stronger read tool instructions |
| `interface/textual_ui/tcss/app.tcss` | New color palette, dark theme, styled all message types, borders, panels |
| `interface/textual_ui/tcss/tools.tcss` | Color palette added, all tool-specific styles updated |
| `interface/textual_ui/widgets/tool_widgets.py` | Generic syntax fix (Python 3.11), removed `edit` from registries, fixed `file_path` access |
| `interface/textual_ui/cli_adapters.py` | F-string backslash fix, separated `edit` display logic |
| `core/tools/__init__.py` | Conditional Windows imports, lazy import system |
| `interface/textual_ui/tui_main.py` | Conditional Windows tool registration |
| `interface/cli/cli.py` | Conditional Windows tool registration |

---

## Remaining Notes

- The `mcp>=1.0.0` dependency was previously added to `pyproject.toml` but may have been reverted by the user. If MCP functionality is needed, re-add it.
- If using a model with **native reasoning** (e.g., Claude extended thinking, OpenAI o1), the system prompt cannot fully suppress reasoning output — that is controlled at the provider/API level.
