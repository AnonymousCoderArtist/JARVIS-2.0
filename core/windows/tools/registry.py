"""Registry tool — Windows Registry operations."""

from typing import Literal, Any

from core.windows.analytics import with_analytics


def create_registry_tool(desktop, analytics=None):
    """Create a registry tool."""
    @with_analytics(analytics, "Registry-Tool")
    def registry_tool(
        mode: Literal['get', 'set', 'delete', 'list'],
        path: str,
        name: str | None = None,
        value: str | None = None,
        type: Literal['String', 'DWord', 'QWord', 'Binary', 'MultiString', 'ExpandString'] = 'String',
    ) -> str:
        try:
            if mode == 'get':
                if name is None:
                    return 'Error: name parameter is required for get mode.'
                return desktop.registry_get(path=path, name=name)
            elif mode == 'set':
                if name is None:
                    return 'Error: name parameter is required for set mode.'
                if value is None:
                    return 'Error: value parameter is required for set mode.'
                return desktop.registry_set(path=path, name=name, value=value, reg_type=type)
            elif mode == 'delete':
                return desktop.registry_delete(path=path, name=name)
            elif mode == 'list':
                return desktop.registry_list(path=path)
            else:
                return 'Error: mode must be "get", "set", "delete", or "list".'
        except Exception as e:
            return f'Error accessing registry: {str(e)}'
    
    return registry_tool