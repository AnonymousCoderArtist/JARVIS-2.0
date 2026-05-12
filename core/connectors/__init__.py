"""Connectors framework for JARVIS - integrates with external data sources"""

from .base import (
    BaseConnector,
    ConnectorConfig,
    Document,
    Attachment,
    SyncStatus,
)
from .registry import ConnectorRegistry, load_connectors
from .filesystem import FilesystemConnector
from .manager import ConnectorManager

__all__ = [
    # Base classes
    "BaseConnector",
    "ConnectorConfig",
    "Document",
    "Attachment",
    "SyncStatus",
    # Registry
    "ConnectorRegistry",
    "load_connectors",
    # Existing
    "FilesystemConnector",
    "ConnectorManager",
]


# Auto-load connectors when imported
def _init():
    """Initialize the connector system"""
    load_connectors()


_init()