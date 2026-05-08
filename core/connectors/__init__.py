"""Connectors framework for JARVIS - integrates with external data sources"""

from .base import BaseConnector, ConnectorConfig
from .filesystem import FilesystemConnector
from .manager import ConnectorManager

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "FilesystemConnector",
    "ConnectorManager",
]
