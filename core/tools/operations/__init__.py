"""Pluggable operation backends for file/bash/edit operations."""

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
from core.tools.operations.registry import OperationsRegistry

__all__ = [
    "BashOperations",
    "EditOperations",
    "FileOperations",
    "LocalBashOperations",
    "LocalEditOperations",
    "LocalFileOperations",
    "OperationsRegistry",
]
