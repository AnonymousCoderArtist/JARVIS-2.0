"""Extension system for JARVIS — internal implementation.

⚠️  For extension development, import from ``jarvis.api`` instead::

    from jarvis.api import ExtensionAPI, ExtensionManifest, ExtensionRunner

This module is kept for internal use and backward compatibility.
"""

from jarvis.core.extensions.api import ExtensionAPI
from jarvis.core.extensions.runner import ExtensionRunner
from jarvis.core.extensions.types import ExtensionManifest

__all__ = [
    "ExtensionAPI",
    "ExtensionManifest",
    "ExtensionRunner",
]
