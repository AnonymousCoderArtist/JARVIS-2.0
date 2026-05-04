"""Clipboard tool — copy/paste clipboard operations."""

from typing import Literal, Any

from core.windows.analytics import with_analytics


def create_clipboard_tool(analytics=None):
    """Create a clipboard tool."""
    @with_analytics(analytics, "Clipboard-Tool")
    def clipboard_tool(
        mode: Literal["get", "set"], text: str | None = None,
    ) -> str:
        try:
            import win32clipboard

            if mode == "get":
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                        data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                        return f"Clipboard content:\n{data}"
                    else:
                        return "Clipboard is empty or contains non-text data."
                finally:
                    win32clipboard.CloseClipboard()
            elif mode == "set":
                if text is None:
                    return "Error: text parameter required for set mode."
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                    return f"Clipboard set to: {text[:100]}{'...' if len(text) > 100 else ''}"
                finally:
                    win32clipboard.CloseClipboard()
            else:
                return 'Error: mode must be either "get" or "set".'
        except Exception as e:
            return f"Error managing clipboard: {str(e)}"
    
    return clipboard_tool