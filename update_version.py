#!/usr/bin/env python3
"""
Version Manager - Update version across all files in the codebase.

Usage:
    python update_version.py 2.0.2          # Update to specific version
    python update_version.py minor          # Bump minor version (2.0.1 -> 2.1.0)
    python update_version.py patch          # Bump patch version (2.0.1 -> 2.0.2)
    python update_version.py major          # Bump major version (2.0.1 -> 3.0.0)
    python update_version.py show           # Show current version
"""

import re
import sys
from pathlib import Path

# Files to update with version
VERSION_FILES = {
    "jarvis/_version.py": r'__version__ = "([^"]+)"',
    "pyproject.toml": r'version = "([^"]+)"',
    "jarvis/__init__.py": r'__version__ = "([^"]+)"',
}

CURRENT_VERSION = "2.0.0"


def read_file(path: Path) -> str:
    """Read file contents."""
    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str) -> None:
    """Write file contents."""
    path.write_text(content, encoding="utf-8")


def get_current_version() -> str:
    """Get current version from jarvis/_version.py."""
    version_file = Path("jarvis/_version.py")
    if not version_file.exists():
        return CURRENT_VERSION

    content = read_file(version_file)
    match = re.search(r'__version__ = "([^"]+)"', content)
    if match:
        return match.group(1)
    return CURRENT_VERSION


def bump_version(version: str, bump_type: str) -> str:
    """Bump version number.
    
    Args:
        version: Current version string (e.g., "2.0.1")
        bump_type: One of "major", "minor", "patch"
    
    Returns:
        New version string
    """
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


def update_file_version(file_path: str, old_version: str, new_version: str) -> bool:
    """Update version in a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"  ⚠ File not found: {file_path}")
        return False

    content = read_file(path)
    pattern = VERSION_FILES.get(file_path)

    if not pattern:
        # Default pattern for other files
        pattern = r'version = "([^"]+)"'

    new_content = re.sub(
        pattern,
        f'version = "{new_version}"' if "version = " in pattern else f'__version__ = "{new_version}"',
        content
    )

    # Check if version was actually updated
    if old_version in content and old_version not in new_content:
        write_file(path, new_content)
        return True
    elif new_version in content:
        return True

    return False


def update_version(new_version: str) -> None:
    """Update version in all files."""
    current = get_current_version()
    print(f"Updating version: {current} → {new_version}")
    print()

    updated_files = []

    for file_path in VERSION_FILES.keys():
        if update_file_version(file_path, current, new_version):
            updated_files.append(file_path)
            print(f"  ✓ Updated {file_path}")
        else:
            print(f"  ✗ Failed to update {file_path}")

    # Also check if jarvis/__init__.py needs to import from _version.py
    init_file = Path("jarvis/__init__.py")
    if init_file.exists():
        content = read_file(init_file)
        if "__version__" in content and "from ._version" not in content:
            # Need to update to import from _version.py
            new_content = re.sub(
                r'__version__ = "([^"]+)"',
                'from ._version import __version__',
                content
            )
            write_file(init_file, new_content)
            print("  ✓ Updated jarvis/__init__.py to import from _version.py")

    print()
    print(f"Successfully updated {len(updated_files)} file(s)!")


def show_version() -> None:
    """Show current version."""
    version = get_current_version()
    print(f"Current version: {version}")

    # Show version info
    parts = version.split(".")
    print(f"  Major: {parts[0]}")
    print(f"  Minor: {parts[1]}")
    print(f"  Patch: {parts[2]}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "show":
        show_version()
    elif command in ("major", "minor", "patch"):
        current = get_current_version()
        new_version = bump_version(current, command)
        update_version(new_version)
    else:
        # Assume it's a version number
        new_version = command
        if not re.match(r'^\d+\.\d+\.\d+$', new_version):
            print("Error: Invalid version format. Use semantic versioning (e.g., 2.0.2)")
            sys.exit(1)
        update_version(new_version)


if __name__ == "__main__":
    main()
