"""JARVIS launcher entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path so interface and core can be found.
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _parse_args(argv: list[str]) -> tuple[bool, list[str]]:
    parser = argparse.ArgumentParser(prog="jarvis", add_help=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="Launch the Rich CLI")
    args, remaining = parser.parse_known_args(argv)
    return args.cli, remaining


def main() -> None:
    """Entry point for the jarvis command."""
    launch_cli, remaining = _parse_args(sys.argv[1:])
    sys.argv = [sys.argv[0], *remaining]

    from interface.cli.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
