"""Base connector framework for JARVIS"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ConnectorConfig:
    """Configuration for a connector"""
    name: str
    connector_type: str
    enabled: bool = True
    priority: int = 0
    config: dict[str, Any] = None  # type: ignore

    def __post_init__(self):
        if self.config is None:
            self.config = {}


class BaseConnector(ABC):
    """Abstract base class for all connectors"""

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.name = config.name

    @abstractmethod
    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch data from the connector source.

        Args:
            query: Search query or identifier
            limit: Maximum number of results

        Returns:
            List of data items with metadata
        """
        pass

    @abstractmethod
    def supports_query_type(self, query_type: str) -> bool:
        """Check if this connector supports a query type.

        Args:
            query_type: Type of query (e.g., 'files', 'web', 'memory')

        Returns:
            True if this connector can handle this query type
        """
        pass

    def get_capabilities(self) -> list[str]:
        """Get list of capabilities this connector provides."""
        return []

    async def search(self, query: str, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Search the connector source. Override for custom search logic."""
        return await self.fetch(query)

    def format_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Format a raw item into a standard format."""
        return {
            "id": item.get("id", item.get("path", str(item))),
            "title": item.get("title", item.get("name", "Untitled")),
            "content": item.get("content", item.get("text", "")),
            "source": self.name,
            "metadata": item.get("metadata", {}),
            "timestamp": item.get("timestamp", item.get("created_at")),
        }
