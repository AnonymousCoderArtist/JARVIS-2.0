"""ExtensionAPI — the surface exposed to every JARVIS extension.

An extension is a Python file that exports a default async function::

    async def jarvis(api: ExtensionAPI):
        \"""Register tools, hooks, commands, and event handlers.\"""
        api.tools(my_tool_instance)
        api.on(ToolCallStarted, my_handler)
        api.hook(HookStage.BEFORE_TOOL_CALL, safety_gate)
        api.command("/hello", hello_cmd, "Say hello")
        api.shortcut("ctrl+alt+h", "app.hello", "Hello shortcut")

Extensions can read their own config from ``settings.json`` under
``extension.<extension_name>``, similar to how watchers use
``watcher.<watcher_name>``::

    // .jarvis/settings.json
    {
        "extension": {
            "ml_intern": {
                "enabled": true,
                "agent_local_tools": ["hf_papers", "hf_jobs", ...]
            }
        }
    }

Call ``api.load_config()`` from your extension's factory function to
retrieve your extension's config dict.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from jarvis.core.events.hooks import HookContext, HookResult, HookStage
from jarvis.core.tools.base import BaseTool

logger = logging.getLogger(__name__)

# Type aliases
EventHandler = Callable[[Any], Coroutine[Any, Any, None] | None]
HookHandler = Callable[[HookContext], Coroutine[Any, Any, HookResult] | HookResult]
CommandHandler = Callable[..., Coroutine[Any, Any, str | None] | str | None]
ShortcutHandler = Callable[[], Coroutine[Any, Any, None] | None]


class ExtensionAPI:
    """The public API surface exposed to extension modules.

    Each extension receives one instance of this class.  The instance is
    pre-configured with the extension's manifest so that tool registrations,
    event subscriptions, etc. can be attributed to the correct extension.
    """

    def __init__(self, extension_name: str, version: str = "1.0.0") -> None:
        # Identifiers
        self._name = extension_name
        self._version = version

        # These are wired in by ExtensionRunner.bind()
        self._tool_registry = None
        self._event_bus = None
        self._hook_registry = None
        self._session = None

        # Accumulated registrations (cleared on bind)
        self._tool_registrations: list[dict] = []
        self._agent_tool_registrations: list[BaseTool] = []
        self._command_registrations: list[dict] = []
        self._event_subscriptions: list[tuple[type, EventHandler]] = []
        self._hook_registrations: list[tuple[HookStage, HookHandler]] = []
        self._shortcut_registrations: list[dict] = []
        self._agent_registrations: list[Any] = []

    # ------------------------------------------------------------------
    # Registration methods (called by the extension at load time)
    # ------------------------------------------------------------------

    def tools(self, tool: Any) -> None:
        """Register a new tool, or override a built-in tool with the same name.

        *tool* can be any object that has ``name``, ``description``,
        ``input_schema``, and an ``async execute(input_data) -> ToolOutput``
        method (i.e. a ``BaseTool`` instance).

        Tools registered via this method are visible globally — all agents
        can discover and call them. For extension-private tools that should
        ONLY be available to this extension's own agent(s), use
        ``agent_tools()`` instead.
        """
        self._tool_registrations.append({"tool": tool})

    def agent_tools(self, tool: BaseTool) -> None:
        """Register a tool that is ONLY available to this extension's agents.

        Unlike ``tools()``, agent-local tools are never included in the main
        agent's function definitions or tool listings. They can only be
        resolved by name from within a ``_FilteredToolRegistry`` that
        explicitly includes them (i.e. from the extension's own subagent).

        *tool* must be a ``BaseTool`` instance.
        """
        self._agent_tool_registrations.append(tool)

    def command(self, name: str, handler: CommandHandler, description: str = "") -> None:
        """Register a slash command (e.g. ``/my-command``)."""
        self._command_registrations.append({
            "name": name,
            "handler": handler,
            "description": description,
        })

    def on(self, event_type: type, handler: EventHandler) -> None:
        """Subscribe to an EventBus event type.

        *handler* receives the event instance when *event_type* is emitted.
        """
        self._event_subscriptions.append((event_type, handler))

    def hook(self, stage: HookStage, handler: HookHandler) -> None:
        """Register a lifecycle hook at *stage*.

        The handler receives a ``HookContext`` and returns a ``HookResult``
        (or a coroutine that does).
        """
        self._hook_registrations.append((stage, handler))

    def shortcut(self, key: str, action_id: str, description: str = "") -> None:
        """Register a keyboard shortcut mapping."""
        self._shortcut_registrations.append({
            "key": key,
            "action_id": action_id,
            "description": description,
        })

    def agents(self, definition: Any) -> None:
        """Register a custom agent definition.

        *definition* should be an ``AgentDefinition`` instance (or any object
        with the required agent attributes).  The agent becomes available via
        the ``agents`` tool and, if ``agent_type=AGENT``, in the profile
        selector (Shift+Tab).
        """
        self._agent_registrations.append(definition)

    # ------------------------------------------------------------------
    # Runtime accessors (valid only after bind())
    # ------------------------------------------------------------------

    @property
    def event_bus(self) -> Any:
        """The session's EventBus (read-only)."""
        return self._event_bus

    @property
    def tool_registry(self) -> Any:
        """The session's ToolRegistry (read-only)."""
        return self._tool_registry

    @property
    def hook_registry(self) -> Any:
        """The session's HookRegistry (read-only)."""
        return self._hook_registry

    @property
    def session(self) -> Any:
        """The current AgentSession (read-only)."""
        return self._session

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    def load_config(self) -> dict:
        """Load extension-specific config from ``settings.json``.

        Config must be under ``extension.<extension_name>``, matching the
        watcher pattern ``watcher.<watcher_name>``::

            // .jarvis/settings.json
            {
                "extension": {
                    "ml_intern": {
                        "enabled": true,
                        "agent_local_tools": ["hf_papers", "hf_jobs"]
                    }
                }
            }

        Returns:
            dict: The extension's config dict, or empty dict if not found.
        """
        settings_path = Path(".jarvis") / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, encoding="utf-8") as f:
                    settings = json.load(f)
                    ext_section = settings.get("extension", {})
                    return ext_section.get(self._name, {})
            except Exception as e:
                logger.debug("Extension %s failed to load config: %s", self._name, e)
        return {}

    # ------------------------------------------------------------------
    # Internal — called by ExtensionRunner
    # ------------------------------------------------------------------

    async def _bind(self, tool_registry, event_bus, hook_registry, session, agent_callback=None) -> list[dict]:
        """Wire this API instance to the live session.

        Called once by ``ExtensionRunner.bind()``. Flushes all queued
        registrations.

        Returns a list of conflict info dicts for tool overrides.
        """
        self._tool_registry = tool_registry
        self._event_bus = event_bus
        self._hook_registry = hook_registry
        self._session = session

        conflicts: list[dict] = []

        # --- Flush tool registrations ---
        for reg in self._tool_registrations:
            tool = reg["tool"]
            existing = tool_registry.get(tool.name)
            if existing is not None:
                logger.info(
                    "Extension '%s' overriding built-in tool '%s'",
                    self._name, tool.name,
                )
                conflicts.append({
                    "extension": self._name,
                    "tool": tool.name,
                    "type": "override",
                })
            tool_registry.register(tool)

        # --- Flush agent-local tool registrations (excluded from global listings) ---
        for tool in self._agent_tool_registrations:
            tool_registry.register_agent_local_tool(tool)

        # --- Flush event subscriptions ---
        if event_bus is not None:
            for event_type, handler in self._event_subscriptions:
                event_bus.subscribe(event_type, handler)

        # --- Flush hook registrations ---
        if hook_registry is not None:
            for stage, handler in self._hook_registrations:
                hook_registry.register(stage, handler)

        # --- Flush agent registrations ---
        if agent_callback is not None:
            for definition in self._agent_registrations:
                agent_callback(definition)

        return conflicts

    async def _unbind(self) -> None:
        """Disconnect this API instance from the session (called on shutdown)."""
        # EventBus / HookRegistry don't support selective handler removal
        # by extension yet — rely on session-level clear().
        self._tool_registry = None
        self._event_bus = None
        self._hook_registry = None
        self._session = None
