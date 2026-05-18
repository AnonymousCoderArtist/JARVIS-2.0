"""Connector Registry - Central registry for all data connectors"""

import logging
from datetime import datetime
from typing import Any

from .base import BaseConnector, ConnectorConfig, Document, SyncStatus

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Central registry for all connectors - similar to OpenJarvis design
    
    Usage:
        @ConnectorRegistry.register("my_connector")
        class MyConnector(BaseConnector):
            ...
        
        # Later, get the connector:
        connector = ConnectorRegistry.get("my_connector")
    """

    _registry: dict[str, type[BaseConnector]] = {}
    _instances: dict[str, BaseConnector] = {}

    @classmethod
    def register(cls, connector_id: str):
        """Decorator to register a connector class
        
        Usage:
            @ConnectorRegistry.register("oura")
            class OuraConnector(BaseConnector):
                ...
        """
        def decorator(connector_class: type[BaseConnector]) -> type[BaseConnector]:
            connector_class.connector_id = connector_id
            cls._registry[connector_id] = connector_class
            logger.debug(f"Registered connector: {connector_id}")
            return connector_class
        return decorator

    @classmethod
    def register_value(cls, connector_id: str, instance: BaseConnector) -> None:
        """Register a pre-instantiated connector"""
        cls._instances[connector_id] = instance
        logger.debug(f"Registered connector instance: {connector_id}")

    @classmethod
    def contains(cls, connector_id: str) -> bool:
        """Check if a connector is registered"""
        return connector_id in cls._registry or connector_id in cls._instances

    @classmethod
    def get(cls, connector_id: str) -> BaseConnector | None:
        """Get a connector by ID, returning a new instance"""
        # First check if we have an existing instance
        if connector_id in cls._instances:
            return cls._instances[connector_id]

        # Otherwise create a new instance
        if connector_id in cls._registry:
            connector_class = cls._registry[connector_id]
            try:
                instance = connector_class()
                cls._instances[connector_id] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to instantiate connector {connector_id}: {e}")
                return None

        return None

    @classmethod
    def get_class(cls, connector_id: str) -> type[BaseConnector] | None:
        """Get a connector class by ID without instantiating"""
        return cls._registry.get(connector_id)

    @classmethod
    def list_connectors(cls) -> list[str]:
        """List all registered connector IDs"""
        all_connectors = set(cls._registry.keys()) | set(cls._instances.keys())
        return sorted(all_connectors)

    @classmethod
    def unregister(cls, connector_id: str) -> bool:
        """Unregister a connector"""
        if connector_id in cls._registry:
            del cls._registry[connector_id]
        if connector_id in cls._instances:
            del cls._instances[connector_id]
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """Clear all registered connectors"""
        cls._registry.clear()
        cls._instances.clear()

    @classmethod
    def get_all_connector_classes(cls) -> dict[str, type[BaseConnector]]:
        """Get all registered connector classes"""
        return cls._registry.copy()

    @classmethod
    def sync_all(
        cls,
        connector_ids: list[str],
        *,
        since: datetime | None = None,
        max_per_connector: int = 15
    ) -> dict[str, list[Document]]:
        """Sync data from multiple connectors
        
        Args:
            connector_ids: List of connector IDs to sync from
            since: Only return items modified after this time
            max_per_connector: Maximum items per connector
            
        Returns:
            Dict mapping connector_id to list of Documents
        """
        results = {}

        for connector_id in connector_ids:
            connector = cls.get(connector_id)
            if not connector:
                logger.warning(f"Connector {connector_id} not found")
                continue

            if not connector.is_connected():
                logger.debug(f"Connector {connector_id} not connected, skipping")
                continue

            try:
                docs = []
                for doc in connector.sync(since=since):
                    docs.append(doc)
                    if len(docs) >= max_per_connector:
                        break
                results[connector_id] = docs
            except Exception as e:
                logger.error(f"Failed to sync {connector_id}: {e}")
                results[connector_id] = []

        return results

    @classmethod
    def get_connection_status(cls) -> dict[str, dict[str, Any]]:
        """Get connection status for all connectors"""
        status = {}

        for connector_id in cls.list_connectors():
            connector = cls.get(connector_id)
            if connector:
                try:
                    status[connector_id] = {
                        "connected": connector.is_connected(),
                        "display_name": getattr(connector, 'display_name', connector_id),
                        "auth_type": getattr(connector, 'auth_type', 'unknown'),
                        "sync_status": connector.sync_status().__dict__.copy() if connector.sync_status() else {},
                    }
                except Exception as e:
                    status[connector_id] = {
                        "connected": False,
                        "error": str(e),
                    }

        return status


# Import this last to avoid circular imports
# The actual connector implementations will register themselves when imported
def load_connectors():
    """Load all built-in connectors
    
    Call this to register all built-in connectors.
    """
    # Import all connector modules to trigger registration
    # The connectors will register themselves via the @ConnectorRegistry.register decorator
    try:
        from . import weather
    except ImportError:
        pass

    try:
        from . import github
    except ImportError:
        pass

    try:
        from . import rss
    except ImportError:
        pass

    try:
        from . import http
    except ImportError:
        pass

    # Also load filesystem (already exists)
    try:
        from . import filesystem
    except ImportError:
        pass

    logger.info(f"Loaded {len(ConnectorRegistry.list_connectors())} connectors")


__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "Document",
    "Attachment",
    "SyncStatus",
    "ConnectorRegistry",
    "load_connectors",
]
