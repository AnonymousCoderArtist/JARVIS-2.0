"""JARVIS launcher entry point"""

import sys
from pathlib import Path

# Add project root to path so main.py can be found
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from main import main as _main  # noqa: E402


def main():
    """Entry point for jarvis command"""
    _main()

if __name__ == "__main__":
    main()
