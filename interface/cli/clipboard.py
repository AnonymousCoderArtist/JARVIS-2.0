"""Clipboard utilities for JARVIS CLI."""


import pyperclip


def copy_to_clipboard(text: str) -> None:
    """Copy text to the system clipboard.

    Args:
        text: The text to copy to clipboard.
    """
    pyperclip.copy(text)


def copy_selection_to_clipboard(text: str) -> None:
    """Copy selected text to clipboard (alias for copy_to_clipboard)."""
    copy_to_clipboard(text)


def get_clipboard_text() -> str:
    """Get text from the clipboard."""
    try:
        return pyperclip.paste()
    except Exception:
        return ""
