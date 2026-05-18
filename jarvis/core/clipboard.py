"""Clipboard utilities for JARVIS."""

from __future__ import annotations


def copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard.

    Args:
        text: The text to copy to clipboard.
    """
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        # Fallback if pyperclip not available
        raise RuntimeError("pyperclip is required for clipboard operations")


def get_clipboard_text() -> str:
    """Get text from the clipboard."""
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        return ""


def copy_image_to_clipboard(image_data: str) -> None:
    """Copy image data to clipboard (for future image support)."""
    # TODO: Implement image clipboard support
    raise NotImplementedError("Image clipboard support not yet implemented")
