"""OperationsRegistry — holds the active backend implementations.

The registry decouples tool implementations from the underlying
filesystem/OS calls.  Extensions can swap backends by registering
alternative ``FileOperations``, ``BashOperations``, or
``EditOperations`` implementations.
"""

from __future__ import annotations

import logging
from typing import Any

from core.tools.operations.base import (
    BashOperations,
    EditOperations,
    FileOperations,
)
from core.tools.operations.local import (
    LocalBashOperations,
    LocalEditOperations,
    LocalFileOperations,
)

logger = logging.getLogger(__name__)


class OperationsRegistry:
    """Holds one active implementation for each operation type.

    Defaults to local implementations.  Extensions can call
    ``set_file_ops()``, ``set_bash_ops()``, or ``set_edit_ops()`` to
    swap backends at runtime.

    Thread-safety
    -------------
    This class is **not** thread-safe.  Each session should own its
    own ``OperationsRegistry`` instance.
    """

    def __init__(self) -> None:
        # Start with local (default) implementations
        self._file_ops: FileOperations = LocalFileOperations()
        self._bash_ops: BashOperations = LocalBashOperations()
        self._edit_ops: EditOperations = LocalEditOperations()

        # Extension name that last changed each backend (for auditing)
        self._file_ops_origin: str = "builtin"
        self._bash_ops_origin: str = "builtin"
        self._edit_ops_origin: str = "builtin"

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    @property
    def file_ops(self) -> FileOperations:
        return self._file_ops

    @property
    def bash_ops(self) -> BashOperations:
        return self._bash_ops

    @property
    def edit_ops(self) -> EditOperations:
        return self._edit_ops

    # ------------------------------------------------------------------
    # Setters (called by extensions)
    # ------------------------------------------------------------------

    def set_file_ops(self, impl: FileOperations, origin: str = "unknown") -> None:
        """Replace the active file operations backend."""
        self._file_ops = impl
        self._file_ops_origin = origin
        logger.info("File operations backend switched to %s by '%s'", type(impl).__name__, origin)

    def set_bash_ops(self, impl: BashOperations, origin: str = "unknown") -> None:
        """Replace the active bash operations backend."""
        self._bash_ops = impl
        self._bash_ops_origin = origin
        logger.info("Bash operations backend switched to %s by '%s'", type(impl).__name__, origin)

    def set_edit_ops(self, impl: EditOperations, origin: str = "unknown") -> None:
        """Replace the active edit operations backend."""
        self._edit_ops = impl
        self._edit_ops_origin = origin
        logger.info("Edit operations backend switched to %s by '%s'", type(impl).__name__, origin)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_backend_info(self) -> dict[str, Any]:
        """Return a dict describing which backends are active."""
        return {
            "file_ops": {
                "class": type(self._file_ops).__name__,
                "origin": self._file_ops_origin,
            },
            "bash_ops": {
                "class": type(self._bash_ops).__name__,
                "origin": self._bash_ops_origin,
            },
            "edit_ops": {
                "class": type(self._edit_ops).__name__,
                "origin": self._edit_ops_origin,
            },
        }

    def reset_all(self) -> None:
        """Restore all backends to the default local implementations."""
        self._file_ops = LocalFileOperations()
        self._bash_ops = LocalBashOperations()
        self._edit_ops = LocalEditOperations()
        self._file_ops_origin = "builtin"
        self._bash_ops_origin = "builtin"
        self._edit_ops_origin = "builtin"
