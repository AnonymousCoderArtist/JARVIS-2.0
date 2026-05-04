"""Process tool — list and kill running processes."""

from typing import Literal, Any

from core.windows.analytics import with_analytics


def create_process_tool(desktop, analytics=None):
    """Create a process tool."""
    @with_analytics(analytics, "Process-Tool")
    def process_tool(
        mode: Literal["list", "kill"],
        name: str | None = None,
        pid: int | None = None,
        sort_by: Literal["memory", "cpu", "name"] = "memory",
        limit: int = 20,
        force: bool | str = False,
    ) -> str:
        try:
            if mode == "list":
                return desktop.list_processes(name=name, sort_by=sort_by, limit=limit)
            elif mode == "kill":
                force = force is True or (isinstance(force, str) and force.lower() == "true")
                return desktop.kill_process(name=name, pid=pid, force=force)
            else:
                return 'Error: mode must be either "list" or "kill".'
        except Exception as e:
            return f"Error managing processes: {str(e)}"
    
    return process_tool