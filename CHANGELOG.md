# JARVIS Changes & Improvements

## Overview

This document summarizes all the fixes, improvements, and UI updates made to the JARVIS project during the current development session.

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

## Files Modified

| File | What Changed |
|------|-------------|
| `core/agents/system_prompts.py` | Complete rewrite of guidelines (16 rules), updated header, stronger read tool instructions |
| `interface/textual_ui/tcss/app.tcss` | New color palette, dark theme, styled all message types, borders, panels |
| `interface/textual_ui/tcss/tools.tcss` | Color palette added, all tool-specific styles updated |
| `interface/textual_ui/widgets/tool_widgets.py` | Generic syntax fix (Python 3.11), removed `edit` from registries, fixed `file_path` access |
| `interface/textual_ui/cli_adapters.py` | F-string backslash fix, separated `edit` display logic |
| `core/tools/__init__.py` | Conditional Windows imports |
| `interface/textual_ui/tui_main.py` | Conditional Windows tool registration |
| `interface/cli/cli.py` | Conditional Windows tool registration |

---

## Remaining Notes

- The `mcp>=1.0.0` dependency was previously added to `pyproject.toml` but may have been reverted by the user. If MCP functionality is needed, re-add it.
- If using a model with **native reasoning** (e.g., Claude extended thinking, OpenAI o1), the system prompt cannot fully suppress reasoning output — that is controlled at the provider/API level.
