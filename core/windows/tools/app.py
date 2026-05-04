"""App tool — launch, resize, switch applications."""

from typing import Literal, Any

from core.windows.analytics import with_analytics


def create_app_tool(desktop, analytics=None):
    """Create an app management tool."""
    @with_analytics(analytics, "App-Tool")
    def app_tool(
        mode: Literal['launch', 'resize', 'switch'] = 'launch',
        name: str | None = None,
        window_loc: list[int] | None = None,
        window_size: list[int] | None = None,
    ) -> Any:
        return desktop.app(mode, name, window_loc, window_size)
    
    return app_tool