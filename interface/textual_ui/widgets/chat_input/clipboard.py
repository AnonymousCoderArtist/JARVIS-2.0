"""Clipboard utilities for image handling."""

from __future__ import annotations

import base64
from pathlib import Path


def image_to_data_url(file_path: Path) -> str:
    """Convert an image file to a data URL.

    Args:
        file_path: Path to the image file.

    Returns:
        Data URL string in format: data:image/<mime>;base64,<data>
    """
    mime_type = _get_image_mime_type(file_path)
    with open(file_path, "rb") as f:
        data = f.read()
    base64_data = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{base64_data}"


def _get_image_mime_type(file_path: Path) -> str:
    """Get the MIME type for an image file based on extension."""
    extension = file_path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return mime_types.get(extension, "image/png")


def read_image_from_clipboard() -> str | None:
    """Read an image from the system clipboard.

    Returns:
        Data URL string if an image is available on clipboard, None otherwise.
    """
    try:
        import pyperclip
    except ImportError:
        return None

    # pyperclip doesn't directly support images, so we use a workaround
    # with tkinter for cross-platform support
    try:
        return _read_image_from_clipboard_tk()
    except Exception:
        return None


def _read_image_from_clipboard_tk() -> str | None:
    """Read image from clipboard using tkinter (cross-platform)."""
    try:
        import io
        import tkinter as tk

        from PIL import Image
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()

    try:
        # Get image data from clipboard
        image = root.clipboard_get()
        if isinstance(image, Image.Image):
            # Convert PIL Image to data URL
            buffer = io.BytesIO()
            image.save(buffer, format=image.format or "PNG")
            base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            mime_type = f"image/{image.format.lower()}" if image.format else "image/png"
            return f"data:{mime_type};base64,{base64_data}"
    except tk.TclError:
        # No image on clipboard
        pass
    finally:
        root.destroy()

    return None
