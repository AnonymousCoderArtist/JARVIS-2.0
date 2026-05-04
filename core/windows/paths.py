"""Path configuration for Windows automation module.

Data is persisted in ~/.jarvis/windows for session tracking.
"""

from pathlib import Path

# Data directory for persisting state
WINDOWS_DATA_DIR = Path.home() / ".jarvis" / "windows"
WINDOWS_DATA_DIR.mkdir(parents=True, exist_ok=True)

# User ID file path
USER_ID_FILE = WINDOWS_DATA_DIR / ".windows-user-id"


def get_windows_data_dir() -> Path:
    """Return the Windows automation data directory."""
    return WINDOWS_DATA_DIR


def get_user_id_file() -> Path:
    """Return the path to the user ID file."""
    return USER_ID_FILE