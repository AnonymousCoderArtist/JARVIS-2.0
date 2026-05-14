# Contributing to JARVIS

## Development Setup

```bash
# Clone the repository
git clone https://github.com/OEvortex/JARVIS.git
cd JARVIS

# Python dependencies (choose one)
uv sync                          # if using uv
pip install -e ".[dev]"          # if using pip

# WebUI frontend dependencies
cd interface/webui && npm install && cd ../..

# Install pre-commit hooks (ruff + eslint)
pip install pre-commit
pre-commit install
```

If no `.pre-commit-config.yaml` exists yet, run linting manually before committing (see [Code Style](#code-style)).

---

## Project Structure

```
JARVIS/
├── core/                  # Python backend
│   ├── agents/            # Agent system (base, managers, subagents)
│   ├── tools/             # Tool system (BaseTool, registry, 20+ tools)
│   ├── llm_sdk/           # LLM provider SDKs (Anthropic, OpenAI, base)
│   ├── provider/          # Dynamic provider configuration
│   ├── config/            # Settings & models
│   ├── connectors/        # External integrations
│   └── llm/               # LLM provider abstraction layer
├── jarvis/                # CLI entry point
├── interface/
│   ├── cli/               # Rich CLI (prompt_toolkit)
│   ├── textual_ui/        # TUI (Textual framework)
│   └── webui/             # WebUI (React + Vite + FastAPI)
├── tests/                 # Python test suite (pytest)
├── docs/                  # Documentation
└── main.py                # Root entry point
```

See **ARCHITECTURE.md** for the full design document.

---

## Development Workflow

### Branch Naming

```
feature/<short-description>
fix/<issue-number>-<short-description>
refactor/<area>-<description>
docs/<what-changed>
```

### Making Changes

- **Python** (`core/`, `jarvis/`, `interface/cli/`, `interface/textual_ui/`): edit → lint (`ruff check .`) → test (`pytest tests/`)
- **TypeScript/React** (`interface/webui/src/`): edit → lint (`npm run lint`) → test (`npm test`) — all from `interface/webui/`
- The WebUI backend in `interface/webui/webui_main.py` is a FastAPI server; run it with `uvicorn interface.webui.webui_main:app --reload`

### Running Dev Servers

```bash
# CLI (no server needed)
python main.py

# TUI
python -m interface.textual_ui.tui_main

# WebUI backend + frontend
uvicorn interface.webui.webui_main:app --reload --port 8000
cd interface/webui && npm run dev
```

---

## Testing

### Python (pytest)

```bash
pytest tests/                         # all tests
pytest tests/ -m "not slow"           # skip slow tests
pytest tests/test_file_tools.py -v    # single file
```

Test conventions:
- Files: `tests/test_*.py`, classes: `Test*`, functions: `test_*`
- Async tests use `asyncio_mode = auto` — no special decorator needed
- Mark slow tests with `@pytest.mark.slow`, integration tests with `@pytest.mark.integration`
- Type hints required on all test functions

### WebUI (vitest)

```bash
cd interface/webui
npm test          # single run
npm run test:watch  # watch mode
```

---

## Code Style

### Python (ruff)

```bash
ruff check .       # lint (E, W, F, I, B, C4, UP rules)
ruff format .      # format (line-length: 100)
```

- All functions and methods **must** have type annotations
- Use `snake_case` for functions/variables, `PascalCase` for classes
- Keep `core/tools/__init__.py` side-effect free (lazy imports via `__getattr__`)
- Use `from __future__ import annotations` at top of every module

### TypeScript (eslint + Prettier)

```bash
cd interface/webui
npm run lint       # eslint src/ --max-warnings 0
```

- Use `camelCase` for variables/functions, `PascalCase` for components
- React components go in `interface/webui/src/components/`
- Shared utilities go in `interface/webui/src/lib/`
- Hooks go in `interface/webui/src/hooks/`

---

## Pull Request Process

1. Create a branch from `main` with a descriptive name (see convention above)
2. Make your changes — include tests for new functionality
3. Run all linters and tests — they must pass
4. Write a concise PR description:
   - **What** changed (1-2 sentences)
   - **Why** it changed (motivation / issue link)
   - **How** to test (instructions or `@pytest.mark` markers)
5. PRs require at least one review. Expect feedback on:
   - Type safety / nullable handling
   - Edge cases in tool input schemas
   - Test coverage for new code paths

---

## Adding a New Tool

Tools live in `core/tools/`. Each tool extends `BaseTool` with a `name`, `description`, `input_schema`, and an `execute` method.

### Step-by-step

1. Create `core/tools/my_tool.py`
2. Implement the tool class extending `BaseTool`
3. Register it in `core/tools/__init__.py` (add to `_LAZY_IMPORTS` and `__all__`)
4. Add tests in `tests/test_my_tool.py`
5. Run `ruff check .` and `pytest tests/`

### Minimal Example

```python
"""My custom tool"""

from __future__ import annotations

from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "A message to process",
            }
        },
        "required": ["message"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        message = input_data.message or ""
        return ToolOutput(
            success=True,
            result=f"Processed: {message}",
        )
```

Then register in `core/tools/__init__.py`:

```python
# In _LAZY_IMPORTS:
"MyTool": "core.tools.my_tool:MyTool",

# In __all__:
"MyTool",
```

---

## Adding a New Provider

Providers wrap LLM APIs. Each provider implements `BaseLLMSDK` from `core/llm_sdk/base/sdk.py`.

### Step-by-step

1. Create `core/llm_sdk/<name>/sdk.py`
2. Implement `BaseLLMSDK` — must define `client`, `generate()`, `generate_with_tools()`, and `get_available_models()`
3. Choose `SdkMode.ANTHROPIC` or `SdkMode.OPENAI` depending on API shape
4. Add a `ProviderConfig` entry in `providers.json` or via the provider manager

### Example skeleton

```python
"""MyProvider SDK implementation"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from core.llm_sdk.base.sdk import (
    BaseLLMSDK,
    GenerationConfig,
    GenerationResponse,
    Message,
)


class MyProviderSDK(BaseLLMSDK):
    @property
    def client(self):
        if self._client is None:
            from my_provider import Client
            self._client = Client(api_key=self.api_key, base_url=self.base_url)
        return self._client

    async def generate(self, messages, config, stream=False):
        ...

    async def generate_with_tools(self, messages, tools, config, stream=False):
        ...

    def get_available_models(self) -> list[str]:
        return ["my-model-v1", "my-model-v2"]
```

Register in `providers.json`:

```json
{
  "my_provider": {
    "provider_id": "my_provider",
    "api_key": "<your-key>",
    "base_url": "https://api.myprovider.com",
    "sdk_mode": "openai",
    "enabled": true,
    "default_model": "my-model-v1"
  }
}
```

---

## WebUI Development

### Component Conventions

- Components live in `interface/webui/src/components/`, grouped by feature (e.g., `settings/`, `techy/`, `thread/`, `ui/`)
- Use **shadcn/ui** primitives from `components/ui/` (already scaffolded with `@radix-ui/*`)
- Shared techy CSS classes (`.techy-panel`, `.techy-dialog`, `.techy-header`, etc.) are defined in `globals.css` — prefer them over inline styles
- New UI primitives should follow shadcn/ui patterns: `cva()` from `class-variance-authority`, `cn()` from `tailwind-merge`

### CSS Variable Theming

All colors are defined as RGB channel variables in `globals.css` under `:root`. To retheme, edit these variables:

```css
:root {
  --brand-r: 26;   --brand-g: 90;   --brand-b: 255;   /* Primary accent */
  --text-bright-r: 200; --text-bright-g: 220; --text-bright-b: 255;
  --panel-bg-start-r: 8;  --panel-bg-start-g: 16;  --panel-bg-start-b: 38;
  /* ... */
}
```

Use them in components as `rgba(var(--brand-r), var(--brand-g), var(--brand-b), <alpha>)`. Never hardcode color values in component files.

See `docs/webui-theme.md` for the full design token reference.

### State Management

There is no global state library. State flows through:

- **`ClientProvider`** (`providers/ClientProvider.tsx`) — React context that provides `JarvisClient`, `token`, and `modelName`
- **Hooks** in `hooks/` — `useJarvisStream()`, `useSessions()`, `useTheme()`, `useAttachedImages()`, `useClipboardAndDrop()`
- **`useClient()`** — accessor hook for the client context (must be inside `<ClientProvider>`)
- Local component state for UI concerns (dialogs, toggles, etc.)

---

## What to Change vs What NOT to Touch (for Contributors)

### Safe to Modify

| Area | Notes |
|------|-------|
| **Adding a new tool** | Create a `BaseTool` subclass, add to `core/tools/__init__.py` `_LAZY_IMPORTS` |
| **Adding a new provider** | Implement `BaseLLMSDK`, add to `providers.json` |
| **Adding a new API endpoint** | Add route in `core/web/server.py`, call it from `interface/webui/src/lib/api.ts` |
| **WebUI component** | Create in `components/` following existing patterns |
| **CSS variables** | Change `:root` values in `globals.css` (never rename existing variables) |
| **New MCP server tool** | Just configure it — no code changes needed |
| **New connector** | Implement `BaseConnector`, register in `core/connectors/` |
| **New agent profile** | Add to `core/agents/builtin_profiles.py` or custom in `~/.jarvis/agents/` |
| **Prompts** | Edit `core/agents/prompts/` |
| **Tests** | Add to `tests/` or `interface/webui/src/tests/` |

### Requires Careful Coordination

| Change | Must Update In Sync |
|--------|---------------------|
| WebSocket message format | `core/web/server.py` + `interface/webui/src/lib/jarvis-client.ts` |
| `useJarvisStream` return type | Hook + all consuming components |
| `ToolInput` / `ToolOutput` models | `core/tools/base.py` + all tools + permission system |
| API endpoint contract | `core/web/server.py` + `interface/webui/src/lib/api.ts` |
| Settings model schema | `core/config/models.py` + existing user config files |
| CSS variable *names* | `globals.css` + all 30+ components referencing them |
| `JarvisClient` constructor | `lib/jarvis-client.ts` + `ClientProvider` + `App.tsx` |

### Never Change Alone (Must Update All Consumers)

- `BaseLLMProvider` interface — every provider SDK + agent loop
- `ConversationHistory` message format — CLI, TUI, WebUI, API endpoints all read it
- Permission data model (`ToolPermission`, `PermissionScope`, etc.) — permission manager, approval UI, and agent loop all depend on these types
