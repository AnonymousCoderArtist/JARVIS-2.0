"""Type definitions for the JARVIS extension system."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeAlias

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from jarvis.core.events.hooks import HookContext, HookResult


# ---------------------------------------------------------------------------
# Extension Manifest
# ---------------------------------------------------------------------------


class ExtensionManifest(BaseModel):
    """Metadata about an installed extension."""

    name: str = Field(..., min_length=1, max_length=64, description="Unique extension name")
    version: str = Field("1.0.0", description="Semantic version string")
    description: str = Field("", max_length=512, description="Human-readable description")
    author: str = Field("", max_length=128, description="Author name or handle")

    # Dependencies — names of other extensions that must be loaded first
    requires: list[str] = Field(default_factory=list, description="Extension dependencies by name")

    # Tools this extension provides (populated at registration time)
    tools: list[str] = Field(default_factory=list, description="Tool names this extension provides")

    # Hook stages this extension uses
    hooks: list[str] = Field(default_factory=list, description="Hook stages this extension hooks into")

    # Optional JSON Schema for extension-specific settings merged into user config
    settings_schema: dict[str, Any] | None = Field(None, description="JSON Schema for extension settings")

    # File path from which this extension was loaded
    source_path: str = Field("", description="Filesystem path this extension was loaded from")


# ---------------------------------------------------------------------------
# Extension API surface types
# ---------------------------------------------------------------------------

#: A handler that receives an event bus event (called with the event instance)
EventHandler: TypeAlias = Callable[[Any], Coroutine[Any, Any, None] | None]

#: A handler for a lifecycle hook (called with a HookContext, returns HookResult)
HookHandler: TypeAlias = Callable[["HookContext"], Coroutine[Any, Any, "HookResult"] | None]  # noqa: F821

#: A slash command handler
CommandHandler: TypeAlias = Callable[..., Coroutine[Any, Any, str | None] | str | None]

#: A keyboard shortcut handler
ShortcutHandler: TypeAlias = Callable[[], Coroutine[Any, Any, None] | None]


# ---------------------------------------------------------------------------
# Extension Context
# ---------------------------------------------------------------------------


@dataclass
class ExtensionContext:
    """Context object passed to extension factories and handlers.

    Provides read-only access to the current agent session state
    and a reference to the active :class:`ExtensionAPI`.
    """
    # The ExtensionAPI instance bound to this extension's session
    api: Any = None  # Avoid circular import — set at runtime

    # Current agent state
    agent_name: str = ""
    model: str = ""
    session_id: str = ""
    cwd: str = ""

    # Working message list (some hooks can modify this)
    messages: list[dict[str, Any]] | None = None

    # Arbitrary extension-local storage (dict survives for session lifetime)
    storage: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tool Registration Record
# ---------------------------------------------------------------------------


@dataclass
class ToolRegistration:
    """Tracks a tool registered by an extension (for override conflict detection)."""
    extension_name: str
    tool_name: str
    is_override: bool  # True if this replaces a built-in tool
    original_tool: Any = None  # Reference to the replaced tool, if any


# ---------------------------------------------------------------------------
# Extension Load Result
# ---------------------------------------------------------------------------


@dataclass
class ExtensionLoadResult:
    """Outcome of loading a single extension file."""
    success: bool
    manifest: ExtensionManifest | None = None
    error: str | None = None
    factory_fn: Callable | None = None  # The extension's default factory
