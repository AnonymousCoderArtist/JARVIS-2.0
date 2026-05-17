"""Keybinding system for JARVIS — namespaced action IDs, JSON config, hot-reload.

Maps physical key sequences to semantic action IDs.
Supports namespaced actions:

- ``jarvis.editor.*`` — movement, deletion, history
- ``jarvis.input.*`` — submission, tab-completion
- ``jarvis.agent.*`` — interrupt, cycle models, thinking level
- ``jarvis.session.*`` — fork, tree, rename
- ``jarvis.view.*`` — scroll, zoom
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Keybinding:
    """A single keybinding mapping."""
    key: str          # e.g. "ctrl+p", "alt+enter", "escape"
    action_id: str    # e.g. "jarvis.model.cycleForward"
    description: str = ""


@dataclass
class Keybindings:
    """Collection of keybindings with migration support."""
    version: int = 2
    bindings: list[Keybinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, str]:
        """Convert to legacy flat dict: ``{action_id: key}``."""
        return {b.action_id: b.key for b in self.bindings}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Keybindings:
        """Parse from JSON (supports both flat and structured formats)."""
        if isinstance(data, list):
            # New format: list of {key, action_id, description?}
            return cls(bindings=[Keybinding(**b) for b in data])
        if isinstance(data, dict):
            if "bindings" in data:
                # Structured format
                return cls(
                    version=data.get("version", 2),
                    bindings=[Keybinding(**b) for b in data["bindings"]],
                )
            # Legacy flat format: {action_id: key}
            return cls(bindings=[Keybinding(key=v, action_id=k) for k, v in data.items()])
        return cls()


# ---------------------------------------------------------------------------
# Default keybindings
# ---------------------------------------------------------------------------

# Legacy action ID → new namespaced action ID migration map
ACTION_ID_MIGRATIONS: dict[str, str] = {
    "cursorUp": "jarvis.editor.cursorUp",
    "cursorDown": "jarvis.editor.cursorDown",
    "cursorLeft": "jarvis.editor.cursorLeft",
    "cursorRight": "jarvis.editor.cursorRight",
    "cursorWordLeft": "jarvis.editor.cursorWordLeft",
    "cursorWordRight": "jarvis.editor.cursorWordRight",
    "cursorHome": "jarvis.editor.cursorHome",
    "cursorEnd": "jarvis.editor.cursorEnd",
    "deleteCharBackward": "jarvis.editor.deleteCharBackward",
    "deleteCharForward": "jarvis.editor.deleteCharForward",
    "deleteWordBackward": "jarvis.editor.deleteWordBackward",
    "deleteWordForward": "jarvis.editor.deleteWordForward",
    "deleteToLineStart": "jarvis.editor.deleteToLineStart",
    "deleteToLineEnd": "jarvis.editor.deleteToLineEnd",
    "yank": "jarvis.editor.yank",
    "yankPop": "jarvis.editor.yankPop",
    "killLine": "jarvis.editor.killLine",
    "undo": "jarvis.editor.undo",
    "redo": "jarvis.editor.redo",
    "newLine": "jarvis.input.newLine",
    "submit": "jarvis.input.submit",
    "tab": "jarvis.input.tab",
    "expandTools": "jarvis.view.expandTools",
    "interrupt": "jarvis.agent.interrupt",
}

# Default bindings (will be used if no keybindings.json exists)
DEFAULT_BINDINGS: list[Keybinding] = [
    # Editor navigation
    Keybinding("up", "jarvis.editor.cursorUp", "Move cursor up"),
    Keybinding("down", "jarvis.editor.cursorDown", "Move cursor down"),
    Keybinding("left", "jarvis.editor.cursorLeft", "Move cursor left"),
    Keybinding("right", "jarvis.editor.cursorRight", "Move cursor right"),
    Keybinding("alt+left", "jarvis.editor.cursorWordLeft", "Move cursor word left"),
    Keybinding("alt+right", "jarvis.editor.cursorWordRight", "Move cursor word right"),
    Keybinding("home", "jarvis.editor.cursorHome", "Move cursor to line start"),
    Keybinding("end", "jarvis.editor.cursorEnd", "Move cursor to line end"),
    # Editor deletion
    Keybinding("backspace", "jarvis.editor.deleteCharBackward", "Delete character backward"),
    Keybinding("delete", "jarvis.editor.deleteCharForward", "Delete character forward"),
    Keybinding("alt+backspace", "jarvis.editor.deleteWordBackward", "Delete word backward"),
    Keybinding("alt+delete", "jarvis.editor.deleteWordForward", "Delete word forward"),
    Keybinding("ctrl+u", "jarvis.editor.deleteToLineStart", "Delete to line start"),
    Keybinding("ctrl+k", "jarvis.editor.deleteToLineEnd", "Delete to line end"),
    Keybinding("ctrl+y", "jarvis.editor.yank", "Paste from kill ring"),
    Keybinding("alt+y", "jarvis.editor.yankPop", "Cycle kill ring"),
    # Editor history
    Keybinding("ctrl+z", "jarvis.editor.undo", "Undo"),
    Keybinding("ctrl+shift+z", "jarvis.editor.redo", "Redo"),
    Keybinding("ctrl+_", "jarvis.editor.undo", "Undo (alternative)"),
    # Input actions
    Keybinding("enter", "jarvis.input.newLine", "Insert new line"),
    Keybinding("alt+enter", "jarvis.input.submit", "Submit message"),
    Keybinding("tab", "jarvis.input.tab", "Autocomplete"),
    # Agent actions
    Keybinding("escape", "jarvis.agent.interrupt", "Interrupt agent"),
    Keybinding("ctrl+l", "jarvis.model.select", "Open model selector"),
    Keybinding("ctrl+p", "jarvis.model.cycleForward", "Cycle model forward"),
    Keybinding("shift+tab", "jarvis.thinking.cycle", "Cycle thinking level"),
    # Session actions
    Keybinding("ctrl+s", "jarvis.session.fork", "Fork session"),
    Keybinding("ctrl+t", "jarvis.session.tree", "Open session tree"),
    # View actions
    Keybinding("ctrl+=", "jarvis.view.zoomIn", "Zoom in"),
    Keybinding("ctrl+-", "jarvis.view.zoomOut", "Zoom out"),
    Keybinding("ctrl+0", "jarvis.view.zoomReset", "Reset zoom"),
    Keybinding("ctrl+e", "jarvis.view.expandTools", "Expand/collapse tools"),
]


# ---------------------------------------------------------------------------
# Keybinding file management
# ---------------------------------------------------------------------------

KEYBINDING_PATHS = [
    Path.home() / ".jarvis" / "keybindings.json",
    Path(".jarvis") / "keybindings.json",
]


def load_keybindings() -> Keybindings:
    """Load keybindings from JSON files, migrating legacy IDs.

    Project-local overrides global defaults.
    """
    merged = Keybindings()

    for path in reversed(KEYBINDING_PATHS):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                kbs = Keybindings.from_dict(data)
                # Migrate legacy action IDs
                for binding in kbs.bindings:
                    if binding.action_id in ACTION_ID_MIGRATIONS:
                        binding.action_id = ACTION_ID_MIGRATIONS[binding.action_id]
                # Merge: project overrides global
                merged.bindings.extend(kbs.bindings)
            except Exception:
                logger.warning("Failed to load keybindings from %s", path)

    # If no user bindings loaded, use defaults
    if not merged.bindings:
        merged = Keybindings(bindings=list(DEFAULT_BINDINGS))

    return merged


def save_keybindings(kbs: Keybindings, path: str | Path | None = None) -> None:
    """Save keybindings to a JSON file."""
    if path is None:
        path = Path.home() / ".jarvis" / "keybindings.json"

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": kbs.version,
        "bindings": [
            {"key": b.key, "action_id": b.action_id, "description": b.description}
            for b in kbs.bindings
        ],
    }
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def resolve_action(action_id: str, kbs: Keybindings | None = None) -> str | None:
    """Find the key for a given action ID."""
    if kbs is None:
        kbs = load_keybindings()
    for binding in kbs.bindings:
        if binding.action_id == action_id:
            return binding.key
    return None


def format_keybinding_help(kbs: Keybindings | None = None) -> str:
    """Format all keybindings as a help string."""
    if kbs is None:
        kbs = load_keybindings()

    lines = ["## Keybindings", ""]
    # Group by namespace
    namespaces: dict[str, list[Keybinding]] = {}
    for b in kbs.bindings:
        ns = ".".join(b.action_id.split(".")[:2])
        namespaces.setdefault(ns, []).append(b)

    for ns in sorted(namespaces):
        lines.append(f"\n### {ns}")
        for b in sorted(namespaces[ns], key=lambda x: x.action_id):
            desc = f" — {b.description}" if b.description else ""
            lines.append(f"- `{b.key}` → `{b.action_id}`{desc}")

    return "\n".join(lines)
