"""Voice manager adapter."""

from dataclasses import dataclass
from typing import Any


@dataclass
class TranscribeState:
    """Transcribe state."""
    active: bool = False


class VoiceManager:
    """Voice manager."""
    pass


class VoiceManagerPort:
    """Voice manager port."""
    pass
