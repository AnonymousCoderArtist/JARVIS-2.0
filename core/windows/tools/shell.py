"""PowerShell tool — shell/command execution."""

from typing import Any

from core.windows.analytics import with_analytics
from core.windows.desktop.powershell import PowerShellExecutor


def create_shell_tool(desktop, analytics=None):
    """Create a shell tool."""
    @with_analytics(analytics, "Powershell-Tool")
    def powershell_tool(command: str, timeout: int = 30) -> str:
        try:
            response, status_code = PowerShellExecutor.execute_command(command, timeout)
            return f"Response: {response}\nStatus Code: {status_code}"
        except Exception as e:
            return f"Error executing command: {str(e)}\nStatus Code: 1"
    
    return powershell_tool