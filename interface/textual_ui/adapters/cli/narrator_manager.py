"""Narrator manager adapter."""

from dataclasses import dataclass
from typing import Any


@dataclass
class NarratorState:
    """Narrator state."""
    enabled: bool = False


class NarratorManager:
    """Narrator manager."""
    
    def __init__(self, config_getter: Any, audio_player: Any, telemetry_client: Any):
        self.config_getter = config_getter
        self.audio_player = audio_player
        self.telemetry_client = telemetry_client
    
    def get_state(self) -> NarratorState:
        """Get narrator state."""
        return NarratorState()


class NarratorManagerPort:
    """Narrator manager port."""
    pass
