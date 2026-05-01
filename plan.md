# Plan: Fix All ty Issues in JARVIS

## TL;DR
Migrate from mypy to ty (Astral's modern Python type checker), configure with progressive strictness, and fix type annotation issues across the entire codebase (core agents, tools, config, LLM providers, and TUI).

---

## Phase 1: Migration Setup
**Goal**: Replace mypy with ty in project configuration

### Steps:
1. **Remove mypy from dependencies**
   - Edit `pyproject.toml`: Remove `"mypy>=1.8.0"` from `[project.optional-dependencies].dev`
   - Edit `pyproject.toml`: Remove entire `[tool.mypy]` section (lines 143-154)

2. **Add ty to dependencies**
   - Edit `pyproject.toml`: Add `"ty>=0.7.0"` to `[project.optional-dependencies].dev`

3. **Configure ty with progressive strictness**
   - Add `[tool.ty.environment]` section with `python_version = "3.10"`
   - Add `[tool.ty.rules]` section with conservative initial settings:
     - `possibly-unresolved-reference = "warn"`
     - `unused-ignore-comment = "warn"`
   - Add `[tool.ty.terminal]` section with `error-on-warning = false` (initially)

4. **Clean up excludes**
   - Update `[tool.black]` exclude: Remove `.mypy_cache` (line 109)
   - Update `[tool.ruff]` exclude: Remove `.mypy_cache` (line 128)

**Relevant files:**
- `c:\Users\koula\Desktop\CODEBASE\Projects\OEvortex\JARVIS\pyproject.toml`

**Verification:**
1. Run `uv sync --all-groups` to install ty
2. Run `uv run ty check --help` to verify ty is installed
3. Run `uv run ty check .` to get baseline error count

---

## Phase 2: Fix Core Type Issues (Parallel)

### 2.1: Fix `core/config/settings.py`
**Issues:**
- Heavy `Any` usage: `dict[str, Any]` in `_config`, `get()`, `get_section()`, `set()`, `tools()`, `model_dump()`
- `_load_toml_module() -> Any` (line 8)
- `value: Any` parameter (line 145)

**Fixes:**
- Replace `dict[str, Any]` with TypedDict or specific config models using Pydantic
- Consider creating a `ConfigDict` type alias if full TypedDict is too verbose
- Type `_load_toml_module` return more specifically

**Relevant file:** `core/config/settings.py`

---

### 2.2: Fix `core/agents/base.py`
**Issues:**
- `self.memory: list[dict[str, Any]]` (line 52)
- `self.context: dict[str, Any]` (line 53)
- Raw `Callable` callbacks: `stream_callback`, `tool_call_callback`, etc. (lines 55-61)
- Untyped methods: `_build_system_prompt()`, `rebuild_system_prompt()`, `clear_memory()` (lines 68, 99, 186)
- `add_session_rule(self, rule)` missing type for `rule` (line 199)

**Fixes:**
- Define callback type aliases: `StreamCallback`, `ToolCallCallback`, etc.
- Type `rule` parameter in `add_session_rule`
- Add return types to untyped methods
- Consider creating typed message structures instead of `dict[str, Any]`

**Relevant file:** `core/agents/base.py`

---

### 2.3: Fix `core/tools/base.py`
**Issues:**
- `result: Any` (line 22)
- `metadata: dict[str, Any] | None` (line 24)
- `input_schema: dict[str, Any]` (line 32)
- `args: dict` without value type (lines 118, 131)
- `get_function_definition() -> dict[str, Any]` (line 74)

**Fixes:**
- Define tool-related type aliases or TypedDicts
- Type `args` parameters as `dict[str, Any]`
- Consider creating `ToolResult`, `ToolMetadata` typed structures

**Relevant file:** `core/tools/base.py`

---

### 2.4: Fix `core/llm/base.py`
**Issues:**
- `messages: list[dict]` bare dict (line 13)
- `tools: list[dict]` bare dict (line 14)
- `-> str | AsyncGenerator` unparameterized (lines 18, 41)

**Fixes:**
- Define `MessageDict`, `ToolDefDict` TypedDicts
- Parameterize `AsyncGenerator[str, None]` or `AsyncGenerator[dict, None]`
- Consider creating typed message models

**Relevant files:**
- `core/llm/base.py`
- `core/llm/sdk_adapter.py`

---

## Phase 3: Fix TUI Type Issues (Parallel with Phase 2)

### 3.1: Fix `interface/textual_ui/types.py`
**Issues:**
- `tool_calls: list[ToolCall] = None` (line 63) - None for non-optional
- `tool_args: dict = None` (line 78) - bare dict, None default
- `result: Any = None` (line 93)
- `ToolCall.function: ToolCallFunction = None` (line 52)

**Fixes:**
- Use `field: Type | None = None` pattern for optional fields
- Type `tool_args` as `dict[str, Any] | None`
- Consider making fields properly optional with `| None`

**Relevant file:** `interface/textual_ui/types.py`

---

### 3.2: Fix `interface/textual_ui/agent_loop.py`
**Issues:**
- `config: Any` (line 117)
- `agent_manager: Any` (line 119)
- Raw `Callable` callbacks (lines 157-159)
- `result: Any` in methods (lines 289, 324)
- Untyped methods: `count_loaded()`, `resume_existing_session()`, `has_file_changes_at()` (lines 580, 627, 637)

**Fixes:**
- Import and use actual types for `config` and `agent_manager`
- Type callbacks properly: `Callable[[str, list[str]], Any]` → more specific
- Add type annotations to untyped methods
- Consider creating type aliases for complex callback signatures

**Relevant file:** `interface/textual_ui/agent_loop.py`

---

### 3.3: Fix remaining TUI files
**Files to check:**
- `interface/textual_ui/app.py` - Many `**kwargs: Any` (lines 1323, 1475, etc.)
- `interface/textual_ui/cli_adapters.py` - `Any` usage
- `interface/textual_ui/handlers/event_handler.py` - Raw `Callable` params

**Fixes:**
- Add specific types instead of `**kwargs: Any` where possible
- Type event handler callbacks
- Standardize on `| None` vs `Optional`

---

## Phase 4: Fix Remaining Core Files (Parallel)

### 4.1: `core/agents/async_manager.py`
**Issues:**
- `dict[str, Any]` in `context`, `completed_tasks`, `failed_tasks`
- `-> Any` in `execute_tool_concurrent()` (line 214)
- `Callable` import without specific typing

**Fixes:**
- Use typed structures instead of `dict[str, Any]`
- Type the return of `execute_tool_concurrent` more specifically

---

### 4.2: `core/llm_sdk/` files
**Files:**
- `core/llm_sdk/openai/sdk.py`
- `core/llm_sdk/anthropic/sdk.py`
- `core/llm_sdk/base/sdk.py`
- `core/llm_sdk/http_client.py`

**Issues:**
- Unparameterized `AsyncGenerator` (many lines)
- `list[dict]` bare dicts
- `dict[str, Any]` usage

**Fixes:**
- Import and use TypedDicts from `core/llm/base.py` or create shared types
- Parameterize all `AsyncGenerator` usage

---

### 4.3: `core/tools/` implementation files
**Files:**
- `core/tools/registry.py`
- `core/tools/file_tools.py`
- `core/tools/code_tools.py`
- etc.

**Fixes:**
- Ensure all methods have proper type annotations
- Reduce `Any` usage by using typed tool input/output structures

---

## Phase 5: Progressive Strictness Increase

After fixing the initial issues:

1. **First pass** (conservative):
   - `possibly-unresolved-reference = "error"`
   - Keep warnings for `Any` usage

2. **Second pass** (medium):
   - Add `disallow-any = "warn"` or equivalent ty rule
   - Fix remaining `Any` usage

3. **Third pass** (strict):
   - Enable strict mode if available
   - `disallow-incomplete-defs = true`
   - `disallow-untyped-defs = true`

**Update `[tool.ty.rules]` incrementally as code is fixed.**

---

## Verification Steps

After each phase:

1. **Run ty check:**
   ```bash
   uv run ty check .
   ```

2. **Run tests:**
   ```bash
   uv run pytest tests/ -q
   ```

3. **Check specific files:**
   ```bash
   uv run ty check core/config/settings.py
   uv run ty check core/agents/base.py
   ```

4. **Count remaining issues:**
   - Track reduction in ty errors/warnings
   - Aim for 0 errors, then 0 warnings

5. **Integration test:**
   - Run the TUI: `uv run jarvis --cli`
   - Verify no runtime type-related errors

---

## Decisions

- **Migration approach**: Full migration from mypy to ty (not parallel)
- **Strictness**: Progressive - start conservative, increase as code is fixed
- **Priority**: All areas fixed systematically, not just one module
- **Type strategy**: Use TypedDict for dict structures, type aliases for callbacks, reduce `Any` usage
- **Scope**: Entire codebase (core + interface)

---

## Excluded from Scope

- Changing runtime behavior (only type annotations)
- Refactoring logic (unless needed for typing)
- Adding new features
- Migration to uv from other package managers (separate task)

---

## Estimated Order of Work

1. Phase 1 (Setup) - ~30 minutes
2. Phase 2.1 (settings.py) - ~45 minutes
3. Phase 2.2 (base.py) - ~1 hour
4. Phase 2.3 (tools/base.py) - ~30 minutes
5. Phase 2.4 (llm/base.py) - ~45 minutes
6. Phase 3.1 (types.py) - ~30 minutes
7. Phase 3.2 (agent_loop.py) - ~1 hour
8. Phase 3.3 (remaining TUI) - ~1 hour
9. Phase 4.1-4.3 (remaining core) - ~2 hours
10. Phase 5 (progressive strictness) - Ongoing

**Total estimated time**: ~7-8 hours of work
