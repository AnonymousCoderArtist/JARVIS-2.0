"""Clipboard adapter."""

def copy_selection_to_clipboard(text: str) -> None:
    """Copy selection to clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        pass


def copy_text_to_clipboard(text: str) -> None:
    """Copy text to clipboard."""
    copy_selection_to_clipboard(text)
