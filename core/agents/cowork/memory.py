"""Memory management for the Cowork Agent"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any


class CoworkMemory:
    """Session-based memory system for the Cowork Agent"""

    def __init__(self, max_entries: int = 1000, retention_days: int = 7):
        self._memory: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.max_entries = max_entries
        self.retention_days = retention_days

    async def add(
        self, key: str, value: Any, scope: str = "session"
    ) -> None:
        """
        Add a memory entry.

        Args:
            key: Memory key identifier
            value: Value to store
            scope: Memory scope ('session', 'persistent', 'context')
        """
        entry = {
            "key": key,
            "value": value,
            "scope": scope,
            "created_at": datetime.utcnow().isoformat(),
            "accessed_at": datetime.utcnow().isoformat(),
        }

        # Move to end and enforce max size
        if key in self._memory:
            self._memory.move_to_end(key)
            self._memory[key] = entry
        else:
            self._memory[key] = entry

        # Cleanup if over limit
        while len(self._memory) > self.max_entries:
            self._memory.popitem(last=False)

    async def get(
        self, key: str, scope: str | None = None
    ) -> Any:
        """
        Retrieve a memory entry by key.

        Args:
            key: Memory key identifier
            scope: Optional scope filter

        Returns:
            Stored value or None if not found
        """
        if key not in self._memory:
            return None

        entry = self._memory[key]

        # Scope filter
        if scope is not None and entry.get("scope") != scope:
            return None

        # Update accessed timestamp
        entry["accessed_at"] = datetime.utcnow().isoformat()
        self._memory.move_to_end(key)

        return entry["value"]

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search memory entries by query string.

        Args:
            query: Search query (matched against keys and string values)
            limit: Maximum number of results

        Returns:
            List of matching memory entries
        """
        query_lower = query.lower()
        results = []

        for key, entry in reversed(self._memory.items()):
            if query_lower in key.lower():
                results.append(entry)
            elif isinstance(entry.get("value"), str) and query_lower in entry["value"].lower():
                results.append(entry)

            if len(results) >= limit:
                break

        return results

    async def summarize(self) -> str:
        """
        Summarize the current session memory.

        Returns:
            Human-readable summary of stored memory
        """
        if not self._memory:
            return "No memory entries stored."

        lines = [f"Memory Summary ({len(self._memory)} entries):", ""]

        # Group by scope
        by_scope: dict[str, list[str]] = {}
        for key, entry in self._memory.items():
            scope = entry.get("scope", "unknown")
            if scope not in by_scope:
                by_scope[scope] = []
            value_summary = str(entry["value"])[:100]
            by_scope[scope].append(f"  - {key}: {value_summary}")

        for scope, entries in by_scope.items():
            lines.append(f"## {scope.upper()} SCOPE")
            lines.extend(entries)
            lines.append("")

        return "\n".join(lines)

    async def delete(self, key: str) -> bool:
        """
        Delete a memory entry.

        Args:
            key: Key of entry to delete

        Returns:
            True if deleted, False if not found
        """
        if key in self._memory:
            del self._memory[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all memory entries"""
        self._memory.clear()

    async def cleanup_expired(self) -> int:
        """
        Remove entries older than retention_days.

        Returns:
            Number of entries removed
        """
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        removed = 0
        keys_to_remove = []

        for key, entry in self._memory.items():
            created = entry.get("created_at", "")
            if created:
                try:
                    if datetime.fromisoformat(created) < cutoff:
                        keys_to_remove.append(key)
                except ValueError:
                    pass

        for key in keys_to_remove:
            del self._memory[key]
            removed += 1

        return removed

    @property
    def entry_count(self) -> int:
        """Number of entries in memory"""
        return len(self._memory)