"""MCP Lifecycle Manager for lazy/eager/keep-alive server management.

Manages server lifecycle modes, idle timeouts, and auto-disconnect behavior.
Inspired by pi-mcp-adapter's McpLifecycleManager.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from .mcp_adapter import MCPClient, MCPServerConfig

if TYPE_CHECKING:
    from .mcp_adapter import MCPRegistry

logger = logging.getLogger(__name__)


class MCPLifecycleManager:
    """Manages lazy/eager/keep-alive server lifecycle.

    Lifecycle modes:
    - lazy (default): Server connects only on first tool call, disconnects after idle_timeout.
    - eager: Server connects at initialization but does NOT auto-reconnect on failure.
    - keep-alive: Server connects at initialization, auto-reconnects on failure via health checks.
    """

    def __init__(self, mcp_registry: MCPRegistry):
        self._registry = mcp_registry
        self._configs: dict[str, MCPServerConfig] = {}
        self._idle_timers: dict[str, asyncio.Task[None]] = {}
        self._health_tasks: dict[str, asyncio.Task[None]] = {}
        self._last_activity: dict[str, float] = {}
        self._shutting_down = False
        self._llm_provider: Any = None
        self._model: str | None = None

    def register_config(self, config: MCPServerConfig) -> None:
        """Register a server config for lifecycle management."""
        self._configs[config.name] = config

    async def initialize_server(self, config: MCPServerConfig) -> None:
        """Initialize a server based on its lifecycle mode.

        - lazy: don't connect yet; just register metadata from cache
        - eager: connect immediately
        - keep-alive: connect immediately + start health check loop
        """
        self.register_config(config)

        if config.lifecycle == "lazy":
            logger.info(f"MCP server '{config.name}' configured as lazy — will connect on first use")
            return

        # eager or keep-alive: connect now
        try:
            await self._ensure_connected(config.name)
            logger.info(f"MCP server '{config.name}' connected ({config.lifecycle} mode)")

            if config.lifecycle == "keep-alive":
                self._start_health_check(config.name)

        except Exception as e:
            if config.lifecycle == "keep-alive":
                logger.warning(f"MCP server '{config.name}' failed to connect (keep-alive will retry): {e}")
                self._start_health_check(config.name)
            else:
                logger.error(f"MCP server '{config.name}' failed to connect (eager mode): {e}")

    async def ensure_connected(self, server_name: str) -> MCPClient:
        """Ensure a server is connected, connecting lazily if needed."""
        return await self._ensure_connected(server_name)

    async def _ensure_connected(self, server_name: str) -> MCPClient:
        """Internal: connect to a server if not already connected."""
        config = self._configs.get(server_name)
        if not config:
            raise ValueError(f"No config registered for MCP server '{server_name}'")

        client = self._registry.get_client(server_name)
        if client and client.is_connected:
            self._touch_activity(server_name)
            return client

        # Need to connect
        logger.info(f"Connecting to MCP server '{server_name}' (lifecycle: {config.lifecycle})")
        client = MCPClient(config, llm_provider=self._llm_provider, model=self._model)
        await client.connect()

        # Register with the registry
        self._registry._clients[server_name] = client

        self._touch_activity(server_name)
        self._start_idle_timer(server_name)

        return client

    async def on_tool_call(self, server_name: str) -> None:
        """Reset idle timer after a tool call."""
        self._touch_activity(server_name)

        # If the server was disconnected and this is a keep-alive, ensure health check is running
        config = self._configs.get(server_name)
        if config and config.lifecycle == "keep-alive" and server_name not in self._health_tasks:
            self._start_health_check(server_name)

    async def disconnect_server(self, server_name: str) -> None:
        """Disconnect a server and clean up its timers."""
        self._cancel_idle_timer(server_name)
        self._cancel_health_check(server_name)

        client = self._registry.get_client(server_name)
        if client:
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting MCP server '{server_name}': {e}")
            self._registry._clients.pop(server_name, None)

    async def shutdown(self) -> None:
        """Shutdown all servers and cancel all timers."""
        self._shutting_down = True

        # Cancel all timers
        for name in list(self._idle_timers.keys()):
            self._cancel_idle_timer(name)

        for name in list(self._health_tasks.keys()):
            self._cancel_health_check(name)

        # Disconnect all servers
        for name in list(self._configs.keys()):
            client = self._registry.get_client(name)
            if client and client.is_connected:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    def _touch_activity(self, server_name: str) -> None:
        """Record activity for a server, resetting idle timer."""
        self._last_activity[server_name] = time.time()

        # Reset idle timer
        config = self._configs.get(server_name)
        if config and config.lifecycle == "lazy" and config.idle_timeout > 0:
            self._start_idle_timer(server_name)

    def _start_idle_timer(self, server_name: str) -> None:
        """Start or restart idle timeout for a lazy server."""
        config = self._configs.get(server_name)
        if not config or config.lifecycle != "lazy" or config.idle_timeout <= 0:
            return
        if self._shutting_down:
            return

        # Cancel existing timer
        self._cancel_idle_timer(server_name)

        timeout_secs = config.idle_timeout * 60  # Convert minutes to seconds

        async def _idle_timeout() -> None:
            try:
                await asyncio.sleep(timeout_secs)
                if self._shutting_down:
                    return
                last = self._last_activity.get(server_name, 0)
                elapsed = time.time() - last
                if elapsed >= timeout_secs - 1:  # Allow 1s tolerance
                    logger.info(f"MCP server '{server_name}' idle timeout reached, disconnecting")
                    await self.disconnect_server(server_name)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"Idle timer error for '{server_name}': {e}")

        self._idle_timers[server_name] = asyncio.create_task(_idle_timeout())

    def _cancel_idle_timer(self, server_name: str) -> None:
        """Cancel idle timer for a server."""
        task = self._idle_timers.pop(server_name, None)
        if task and not task.done():
            task.cancel()

    def _start_health_check(self, server_name: str) -> None:
        """Start periodic health check for a keep-alive server."""
        config = self._configs.get(server_name)
        if not config or config.lifecycle != "keep-alive":
            return
        if self._shutting_down:
            return

        # Cancel existing health check
        self._cancel_health_check(server_name)

        async def _health_loop() -> None:
            while not self._shutting_down:
                try:
                    await asyncio.sleep(30)  # Check every 30 seconds
                    if self._shutting_down:
                        return

                    client = self._registry.get_client(server_name)
                    if client and client.is_connected:
                        continue

                    # Server died, try to reconnect
                    logger.info(f"MCP server '{server_name}' disconnected, reconnecting (keep-alive)...")
                    try:
                        await self._ensure_connected(server_name)
                        logger.info(f"MCP server '{server_name}' reconnected")
                    except Exception as e:
                        logger.warning(f"Failed to reconnect MCP server '{server_name}': {e}")

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.warning(f"Health check error for '{server_name}': {e}")

        self._health_tasks[server_name] = asyncio.create_task(_health_loop())

    def _cancel_health_check(self, server_name: str) -> None:
        """Cancel health check for a server."""
        task = self._health_tasks.pop(server_name, None)
        if task and not task.done():
            task.cancel()

    def get_status(self, server_name: str) -> dict[str, Any]:
        """Get lifecycle status for a server."""
        config = self._configs.get(server_name)
        client = self._registry.get_client(server_name)
        last_activity = self._last_activity.get(server_name, 0)

        return {
            "name": server_name,
            "lifecycle": config.lifecycle if config else "unknown",
            "connected": client.is_connected if client else False,
            "idle_timeout": config.idle_timeout if config else 0,
            "last_activity": last_activity,
            "idle_seconds": time.time() - last_activity if last_activity > 0 else None,
        }
