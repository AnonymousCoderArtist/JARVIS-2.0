"""Watcher Manager for discovering and running watchers"""

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

from jarvis.core.watchers.base import BaseWatcher

logger = logging.getLogger(__name__)

class WatcherManager:
    """Manages discovery and lifecycle of passive watchers"""

    def __init__(self, config_getter=None, event_queue=None):
        self.watchers: dict[str, BaseWatcher] = {}
        self.config_getter = config_getter
        self.event_queue = event_queue
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def register(self, watcher: BaseWatcher):
        """Register a watcher instance"""
        if self.event_queue:
            watcher.set_event_queue(self.event_queue)
        self.watchers[watcher.name] = watcher
        logger.info(f"Registered watcher: {watcher.name}")

    def load_plugin(self, plugin_path: str):
        """Dynamically load a watcher plugin"""
        try:
            path = Path(plugin_path)
            if not path.exists():
                return

            spec = importlib.util.spec_from_file_location(
                f"watcher_plugin_{path.stem}", plugin_path
            )
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"watcher_plugin_{path.stem}"] = module
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseWatcher)
                    and attr != BaseWatcher
                ):
                    try:
                        watcher_instance = attr()
                        self.register(watcher_instance)
                    except Exception:
                        pass  # Silently suppress

        except Exception:
            pass  # Silently suppress

    def discover_watchers(self):
        """Discover watchers from .jarvis/watchers/ subdirectories"""
        search_paths = [
            Path.home() / ".jarvis" / "watchers",
            Path.cwd() / ".jarvis" / "watchers",
        ]

        for path in search_paths:
            if path.exists() and path.is_dir():
                # Look for subdirectories with __init__.py
                for entry in path.iterdir():
                    if entry.is_dir():
                        init_file = entry / "__init__.py"
                        if init_file.exists():
                            self.load_plugin(str(init_file))
                    elif entry.is_file() and entry.suffix == ".py" and entry.name != "__init__.py":
                        # Also support single-file watchers for backward compatibility if desired,
                        # but the requirement was for directory-based __init__.py registration.
                        # I'll stick strictly to the new requirement.
                        pass

    async def start(self):
        """Start all registered watchers"""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting {len(self.watchers)} watchers")

        for watcher in self.watchers.values():
            if watcher.enabled:
                task = asyncio.create_task(self._run_watcher(watcher))
                self._tasks.append(task)

    async def stop(self):
        """Stop all running watchers"""
        self._running = False
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run_watcher(self, watcher: BaseWatcher):
        """Internal loop for a single watcher."""
        while self._running:
            try:
                await watcher.watch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in watcher {watcher.name}: {e}")

            await asyncio.sleep(watcher.interval)
