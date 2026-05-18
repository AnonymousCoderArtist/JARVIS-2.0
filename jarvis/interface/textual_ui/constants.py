from __future__ import annotations

from enum import StrEnum

# Import version from jarvis package
try:
    from jarvis._version import __version__
    CORE_VERSION = __version__
except ImportError:
    CORE_VERSION = "2.1.0"


class MistralColors(StrEnum):
    RED = "#E10500"
    ORANGE_DARK = "#FA500F"
    ORANGE = "#FF8205"
    ORANGE_LIGHT = "#FFAF00"
    YELLOW = "#FFD800"
