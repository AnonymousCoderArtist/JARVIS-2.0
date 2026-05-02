from __future__ import annotations

from enum import StrEnum

# Import version from jarvis package
from jarvis import __version__ as CORE_VERSION


class MistralColors(StrEnum):
    RED = "#E10500"
    ORANGE_DARK = "#FA500F"
    ORANGE = "#FF8205"
    ORANGE_LIGHT = "#FFAF00"
    YELLOW = "#FFD800"
