"""Prompt Templates — markdown files with YAML frontmatter that auto-register as slash commands.

Inspired by `pi`'s prompt template system.  Any ``.md`` file placed in
``.jarvis/prompts/`` or ``~/.jarvis/prompts/`` with YAML frontmatter
automatically becomes a **slash command** the user can invoke (e.g.
``/review``, ``/test``, ``/deploy``).

Template format
---------------
.. code-block:: markdown

    ---
    description: "Review a pull request"
    argument-hint: "<PR-URL>"
    dangerous: false
    ---

    Review the PR at $ARGUMENTS.  Focus on:
    1. Logic errors and bugs
    2. Test coverage
    3. Performance concerns

Argument substitution
---------------------
- ``$1``, ``$2`` — Positional arguments
- ``$@`` or ``$ARGUMENTS`` — All arguments joined by space
- ``${@:N}`` — Arguments from index *N* onwards
- ``${@:N:L}`` — *L* arguments starting from index *N*
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class PromptTemplate:
    """A parsed markdown template file.

    The *name* (derived from the filename stem) becomes the slash command:
    ``pr.md`` → ``/pr``.
    """
    name: str
    file_path: str
    description: str
    body: str
    argument_hint: str = ""
    dangerous: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Separate YAML frontmatter from the markdown body.

    Returns ``(frontmatter_dict, body_string)``.  If no frontmatter is
    found, returns an empty dict and the original content.
    """
    # Match content between opening and closing --- markers
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return {}, content.strip()

    raw_yaml = match.group(1)
    body = match.group(2).strip()

    try:
        import yaml
        frontmatter = yaml.safe_load(raw_yaml) or {}
    except Exception:
        logger.warning("Failed to parse YAML frontmatter, treating as plain body")
        return {}, content.strip()

    if not isinstance(frontmatter, dict):
        return {}, content.strip()

    return frontmatter, body


# ---------------------------------------------------------------------------
# Argument substitution
# ---------------------------------------------------------------------------


def substitute_args(template_body: str, args: list[str]) -> str:
    """Replace positional placeholders in *template_body*.

    Supports::

        $1, $2 …        Positional arguments (1-indexed)
        $@ / $ARGUMENTS  All arguments joined by space
        ${@:N}           Arguments from index N (1-indexed)
        ${@:N:L}         L arguments starting at N
    """
    text = template_body

    # ${@:N:L} — slice of arguments
    def _replace_slice(m: re.Match) -> str:
        n = int(m.group(1)) - 1
        l_val = int(m.group(2)) if m.group(2) else len(args) - n
        return " ".join(args[n : n + l_val])

    text = re.sub(r"\$\{@:(\d+):(\d+)\}", _replace_slice, text)
    text = re.sub(r"\$\{@:(\d+)\}", lambda m: " ".join(args[int(m.group(1)) - 1:]), text)

    # $@ or $ARGUMENTS
    text = text.replace("$ARGUMENTS", " ".join(args))
    text = text.replace("$@", " ".join(args))

    # $1, $2 … — positional
    for i, arg in enumerate(args, start=1):
        text = text.replace(f"${i}", arg)

    return text


def parse_command_args(command_line: str) -> list[str]:
    """Split a command line into arguments, respecting quoted strings.

    ``/review "https://pr.url"`` → ``["/review", "https://pr.url"]``
    """
    # Simple shell-like parsing
    args: list[str] = []
    current: list[str] = []
    in_quote: str | None = None

    for char in command_line:
        if in_quote:
            if char == in_quote:
                in_quote = None
            else:
                current.append(char)
        elif char in ('"', "'"):
            in_quote = char
        elif char == " ":
            if current:
                args.append("".join(current))
                current = []
        else:
            current.append(char)

    if current:
        args.append("".join(current))

    return args


# ---------------------------------------------------------------------------
# Loading & Discovery
# ---------------------------------------------------------------------------


def load_template_from_file(path: str | Path) -> PromptTemplate | None:
    """Load a single markdown file as a ``PromptTemplate``."""
    p = Path(path)
    if not p.exists():
        return None

    try:
        content = p.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to read template file %s", path)
        return None

    frontmatter, body = parse_frontmatter(content)
    if not body:
        logger.warning("Template %s has no body content", path)
        return None

    return PromptTemplate(
        name=p.stem,
        file_path=str(p.resolve()),
        description=frontmatter.get("description", "") or "",
        argument_hint=frontmatter.get("argument-hint", frontmatter.get("argument_hint", "")),
        dangerous=frontmatter.get("dangerous", False),
        body=body,
        metadata=frontmatter,
    )


def load_templates_from_dir(directory: str | Path) -> list[PromptTemplate]:
    """Load all ``.md`` files from *directory*."""
    d = Path(directory)
    if not d.exists() or not d.is_dir():
        return []

    templates: list[PromptTemplate] = []
    for f in sorted(d.glob("*.md")):
        tpl = load_template_from_file(f)
        if tpl is not None:
            templates.append(tpl)
    return templates


# ---------------------------------------------------------------------------
# Slash command formatting
# ---------------------------------------------------------------------------


def format_template_help(templates: list[PromptTemplate]) -> str:
    """Return a help string listing all loaded templates as slash commands."""
    if not templates:
        return ""

    lines = ["## Prompt Templates (Slash Commands)", ""]
    for tpl in sorted(templates, key=lambda t: t.name):
        hint = f" {tpl.argument_hint}" if tpl.argument_hint else ""
        dangerous_mark = " ⚠️" if tpl.dangerous else ""
        lines.append(f"- **`/{tpl.name}{hint}`**{dangerous_mark} — {tpl.description}")
    lines.append("")
    lines.append("Usage: `/template-name arg1 arg2`")
    return "\n".join(lines)
