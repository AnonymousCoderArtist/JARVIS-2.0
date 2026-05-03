"""Connector manager for JARVIS"""

import asyncio
from typing import Any

from .base import BaseConnector, ConnectorConfig


class ConnectorManager:
    """Manages all data connectors for JARVIS"""

    def __init__(self):
        self.connectors: dict[str, BaseConnector] = {}
        self._default_connector: BaseConnector | None = None

    def register(self, connector: BaseConnector) -> None:
        """Register a connector."""
        self.connectors[connector.name] = connector

    def unregister(self, name: str) -> bool:
        """Unregister a connector."""
        if name in self.connectors:
            del self.connectors[name]
            return True
        return False

    def get(self, name: str) -> BaseConnector | None:
        """Get a connector by name."""
        return self.connectors.get(name)

    async def fetch_all(
        self,
        query: str,
        query_types: list[str] | None = None,
        limit_per_connector: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch from all connectors."""
        tasks = []

        for connector in self.connectors.values():
            if query_types:
                # Check if connector supports any of the query types
                if not any(connector.supports_query_type(qt) for qt in query_types):
                    continue

            tasks.append(self._fetch_from_connector(connector, query, limit_per_connector))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for result in results:
            if isinstance(result, list):
                all_items.extend(result)

        return all_items

    async def _fetch_from_connector(
        self,
        connector: BaseConnector,
        query: str,
        limit: int
    ) -> list[dict[str, Any]]:
        """Fetch from a single connector with error handling."""
        try:
            items = await connector.fetch(query, limit)
            return [connector.format_item(item) for item in items]
        except Exception as e:
            print(f"Connector {connector.name} failed: {e}")
            return []

    def get_supported_types(self) -> list[str]:
        """Get all query types supported by registered connectors."""
        types = set()
        for connector in self.connectors.values():
            # Default supported types
            types.update(["files", "filesystem", "code", "documents"])
        return list(types)

    def configure_default_connector(self, name: str) -> None:
        """Set the default connector."""
        self._default_connector = self.connectors.get(name)

    @property
    def default_connector(self) -> BaseConnector | None:
        return self._default_connector