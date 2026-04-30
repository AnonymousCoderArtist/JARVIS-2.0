"""Commands adapter."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CommandAvailabilityContext:
    """Command availability context."""
    pass


class CommandRegistry:
    """Command registry."""
    
    def __init__(self):
        self._commands = {}
    
    def register(self, name: str, handler: Any) -> None:
        """Register command."""
        self._commands[name] = handler
    
    def get(self, name: str) -> Any:
        """Get command."""
        return self._commands.get(name)
