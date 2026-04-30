"""Stderr guard adapter."""

from contextlib import contextmanager


@contextmanager
def stderr_guard():
    """Context manager to guard stderr."""
    yield
