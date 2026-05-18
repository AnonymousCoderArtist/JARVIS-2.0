"""Prompt injector hook — adds custom context to the system prompt.

Register this hook at BEFORE_SYSTEM_PROMPT to inject additional instructions
or project-specific context into every LLM interaction.
"""

from jarvis.core.events.hooks import HookContext, HookResult


async def inject_project_rules(ctx: HookContext) -> HookResult:
    """Inject project-specific rules into the system prompt.

    This hook runs at BEFORE_SYSTEM_PROMPT stage. It appends custom
    instructions that the LLM must follow for this project.
    """
    additional_context = """

## Project-Specific Rules

- Always use `uv` instead of `pip` for Python package management
- Run `ruff check .` before committing any Python changes
- Run `ruff format .` to auto-format Python code
- Use `ty check .` for type checking instead of mypy
- All new code must include type annotations
- Tests must be written with pytest, not unittest
- Never modify files outside the project directory
- When in doubt, ask before making destructive changes
"""

    return HookResult(
        proceed=True,
        inject=additional_context,
    )


async def inject_security_policy(ctx: HookContext) -> HookResult:
    """Inject security policy into the system prompt."""
    security_rules = """

## Security Policy

- Never log sensitive: API keys, passwords, tokens, PII
- Always parameterize SQL queries — never string interpolation
- Validate all user input before processing
- Use HTTPS for all external API calls
- Rotate secrets if they appear in git history
"""

    return HookResult(
        proceed=True,
        inject=security_rules,
    )
