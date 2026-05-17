"""Enhanced base connector framework for JARVIS - compatible with OpenJarvis design"""

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Document Schema - Unified format for all connector data
# -------------------------------------------------------------------


@dataclass
class Attachment:
    """A file attached to a document (email attachment, shared file, etc.)"""
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str = ""
    content: bytes = field(default=b"")


@dataclass
class Document:
    """Universal schema for data from any connector.
    
    All connectors normalize their output to this format before ingestion.
    This is compatible with OpenJarvis's Document schema.
    """
    doc_id: str
    source: str
    doc_type: str
    content: str
    title: str = ""
    author: str = ""
    participants: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    thread_id: str | None = None
    url: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "doc_id": self.doc_id,
            "source": self.source,
            "doc_type": self.doc_type,
            "content": self.content,
            "title": self.title,
            "author": self.author,
            "participants": self.participants,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "thread_id": self.thread_id,
            "url": self.url,
            "metadata": self.metadata,
        }


@dataclass
class SyncStatus:
    """Progress of a connector's sync operation"""
    state: str = "idle"  # idle, syncing, error
    items_synced: int = 0
    items_total: int = 0
    last_sync: datetime | None = None
    cursor: str | None = None
    error: str | None = None


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------


@dataclass
class ConnectorConfig:
    """Configuration for a connector"""
    name: str
    connector_type: str
    enabled: bool = True
    priority: int = 0
    config: dict[str, Any] = None  # type: ignore
    # Auth configuration
    auth_type: str = "none"  # "oauth", "token", "api_key", "none"
    credentials_path: str = ""

    def __post_init__(self):
        if self.config is None:
            self.config = {}

    def get_credential(self, key: str, default: Any = "") -> Any:
        """Get a credential from config"""
        return self.config.get(key, default)


# -------------------------------------------------------------------
# Base Connector
# -------------------------------------------------------------------


class BaseConnector(ABC):
    """Abstract base class for all connectors.
    
    This is compatible with OpenJarvis's BaseConnector design.
    Each connector knows how to:
    - Authenticate with a service
    - Sync its data as Document objects
    - Check connection status
    """

    connector_id: str = ""
    display_name: str = ""
    auth_type: str = "none"  # "oauth" | "token" | "api_key" | "local" | "none"

    def __init__(self, config: ConnectorConfig | None = None):
        self.config = config or ConnectorConfig(
            name=getattr(self.__class__, 'connector_id', 'base'),
            connector_type="base"
        )
        self.name = self.config.name or getattr(self.__class__, 'connector_id', 'base')
        self._status = SyncStatus()

    @property
    def connector_name(self) -> str:
        """Return the connector ID"""
        return getattr(self.__class__, 'connector_id', self.name)

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the connector has valid credentials"""

    @abstractmethod
    def disconnect(self) -> None:
        """Revoke credentials and clean up"""

    @abstractmethod
    def sync(
        self, *, since: datetime | None = None, cursor: str | None = None
    ) -> Iterator[Document]:
        """Yield documents from the data source.
        
        If since is given, only return items created/modified after that time.
        If cursor is given, resume from a previous checkpoint.
        """

    @abstractmethod
    def sync_status(self) -> SyncStatus:
        """Return current sync progress"""

    # --- Legacy methods (for backward compatibility) ---

    @abstractmethod
    async def fetch(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch data from the connector source (legacy method)"""
        pass

    @abstractmethod
    def supports_query_type(self, query_type: str) -> bool:
        """Check if this connector supports a query type"""
        pass

    def get_capabilities(self) -> list[str]:
        """Get list of capabilities this connector provides"""
        return []

    async def search(self, query: str, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Search the connector source. Override for custom search logic."""
        return await self.fetch(query)

    def format_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Format a raw item into a standard format (legacy)"""
        return {
            "id": item.get("id", item.get("path", str(item))),
            "title": item.get("title", item.get("name", "Untitled")),
            "content": item.get("content", item.get("text", "")),
            "source": self.name,
            "metadata": item.get("metadata", {}),
            "timestamp": item.get("timestamp", item.get("created_at")),
        }

    # --- Helper methods ---

    def _load_credentials(self) -> dict[str, str]:
        """Load credentials from the credentials file"""
        import os
        from pathlib import Path

        cred_path = self.config.credentials_path or os.path.join(
            os.path.expanduser("~"),
            ".jarvis",
            "credentials",
            f"{self.connector_name}.json"
        )

        if Path(cred_path).exists():
            try:
                with open(cred_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load credentials for {self.connector_name}: {e}")

        return {}

    def _save_credentials(self, credentials: dict[str, Any]) -> None:
        """Save credentials to the credentials file"""
        import os
        from pathlib import Path

        cred_path = self.config.credentials_path or os.path.join(
            os.path.expanduser("~"),
            ".jarvis",
            "credentials",
            f"{self.connector_name}.json"
        )

        Path(cred_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cred_path, "w") as f:
            json.dump(credentials, f, indent=2)

    def auth_url(self) -> str:
        """Generate an OAuth consent URL. Only relevant for auth_type='oauth'"""
        raise NotImplementedError(f"{self.connector_id} does not use OAuth")

    def handle_callback(self, code: str) -> None:
        """Handle the OAuth callback. Only relevant for auth_type='oauth'"""
        raise NotImplementedError(f"{self.connector_id} does not use OAuth")

    def set_credentials(self, **kwargs: Any) -> None:
        """Set credentials for the connector. Override in subclasses."""
        pass

    def set_api_key(self, api_key: str) -> None:
        """Set API key for the connector. Override in subclasses."""
        pass

    def set_default_headers(self, headers: dict[str, str]) -> None:
        """Set default headers for the connector. Override in subclasses."""
        pass


# -------------------------------------------------------------------
# Decorator for easy registration
# -------------------------------------------------------------------


def register_connector(connector_class: type):
    """Decorator to register a connector class"""
    # This will be handled by the ConnectorRegistry
    # The registry will import all connectors and call register on them
    return connector_class
