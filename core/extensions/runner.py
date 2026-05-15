"""ExtensionRunner — manages the lifecycle of extensions within a session.

Binds loaded extensions to the active ``AgentSession`` by wiring their
``ExtensionAPI`` instances to the session's ``EventBus``, ``HookRegistry``,
and ``ToolRegistry``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.extensions.api import ExtensionAPI
from core.extensions.loader import (
    ExtensionLoadResult,
    discover_and_load_all,
)
from core.extensions.registry import ExtensionRegistry
from core.extensions.types import ExtensionManifest

logger = logging.getLogger(__name__)


class ExtensionRunner:
    """Orchestrates the lifecycle of extensions for a single session.

    Usage
    -----
    .. code-block:: python

        runner = ExtensionRunner()
        results = await runner.discover_and_load(project_dir=".")
        await runner.bind(tool_registry, event_bus, hook_registry, session)
        # ... agent runs ...
        await runner.unbind()
    """

    def __init__(self) -> None:
        self._registry = ExtensionRegistry()

        # Loaded but *not yet bound* — populated by discover_and_load()
        self._pending: list[tuple[ExtensionManifest, Any]] = []

        # Bound API instances — populated by bind()
        self._bound_apis: list[ExtensionAPI] = []

        self._tool_registry = None
        self._event_bus = None
        self._hook_registry = None
        self._session = None

    # ------------------------------------------------------------------
    # Discovery & Loading
    # ------------------------------------------------------------------

    async def discover_and_load(
        self,
        project_dir: str | None = None,
        extra_paths: list[str | Path] | None = None,
    ) -> list[ExtensionLoadResult]:
        """Scan all discovery paths, load every extension, and queue them.

        Returns the list of load results (caller can inspect for errors).
        """
        results = discover_and_load_all(project_dir, extra_paths)
        for result in results:
            if result.success and result.manifest and result.factory_fn:
                self._pending.append((result.manifest, result.factory_fn))
                self._registry.register(result.manifest)
                logger.info(
                    "Loaded extension '%s' v%s from %s",
                    result.manifest.name,
                    result.manifest.version,
                    result.manifest.source_path,
                )
            elif not result.success:
                logger.warning("Failed to load extension: %s", result.error)
        return results

    # ------------------------------------------------------------------
    # Binding
    # ------------------------------------------------------------------

    async def bind(
        self,
        tool_registry: Any,
        event_bus: Any,
        hook_registry: Any,
        session: Any = None,
    ) -> dict[str, list[dict]]:
        """Bind all pending (loaded) extensions to the live session.

        For each extension:
        1. Create an ``ExtensionAPI`` instance
        2. Call the extension's factory function with the API
        3. Flush queued registrations (tools, hooks, events) via
           ``api._bind()``

        Returns a dict mapping extension names to their tool-override
        conflict info.
        """
        self._tool_registry = tool_registry
        self._event_bus = event_bus
        self._hook_registry = hook_registry
        self._session = session

        all_conflicts: dict[str, list[dict]] = {}

        for manifest, factory_fn in self._pending:
            api = ExtensionAPI(
                extension_name=manifest.name,
                version=manifest.version,
            )

            try:
                # Call the extension factory — this populates api.* queues
                result = factory_fn(api)
                if hasattr(result, "__await__"):
                    await result

                # Flush queued registrations into the live components
                conflicts = await api._bind(
                    tool_registry,
                    event_bus,
                    hook_registry,
                    session,
                    operations_registry=getattr(tool_registry, "operations_registry", None),
                )

                if conflicts:
                    all_conflicts[manifest.name] = conflicts
                    for c in conflicts:
                        logger.info(
                            "Extension '%s' overrode tool '%s'",
                            manifest.name, c["tool"],
                        )

                # Update manifest with tools that were registered
                # (approximate — we track from the API registrations)
                manifest.tools = [
                    reg["tool"].name
                    for reg in api._tool_registrations
                ]

                self._bound_apis.append(api)

            except Exception as exc:
                logger.exception(
                    "Failed to bind extension '%s': %s",
                    manifest.name, exc,
                )

        # Clear pending queue
        self._pending.clear()

        return all_conflicts

    # ------------------------------------------------------------------
    # Unbinding
    # ------------------------------------------------------------------

    async def unbind(self) -> None:
        """Disconnect all bound extensions from the session.

        The session's EventBus and HookRegistry should be cleared
        separately (via ``clear()``) to remove all handler references.
        """
        for api in self._bound_apis:
            try:
                await api._unbind()
            except Exception:
                logger.exception("Failed to unbind extension '%s'", api.name)

        self._bound_apis.clear()

    # ------------------------------------------------------------------
    # Deferred hook binding
    # ------------------------------------------------------------------

    def rebind_hooks(self, hook_registry) -> None:
        """Wire pending hook registrations into a live HookRegistry.

        Called after the agent is created (which owns the HookRegistry).
        This allows extensions registered at load time to have their hooks
        active even though the HookRegistry didn't exist at bind() time.
        """
        for api in self._bound_apis:
            for stage, handler in api._hook_registrations:
                hook_registry.register(stage, handler)

    # ------------------------------------------------------------------
    # Runtime accessors
    # ------------------------------------------------------------------

    @property
    def registry(self) -> ExtensionRegistry:
        return self._registry

    @property
    def bound_apis(self) -> list[ExtensionAPI]:
        return list(self._bound_apis)

    @property
    def extension_count(self) -> int:
        return len(self._bound_apis) + len(self._pending)
