"""JARVIS launcher entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to path so interface and core can be found.
project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def _load_env_config() -> dict[str, str]:
    """Load configuration from .env file if it exists."""
    try:
        from dotenv import load_dotenv

        env_path = Path.cwd() / ".env"

        if env_path.exists():
            load_dotenv(env_path)

    except ImportError:
        pass

    return {
        "model": os.getenv("JARVIS_MODEL") or "gpt-4o",
        "base_url": os.getenv("JARVIS_BASE_URL") or "",
        "apikey": os.getenv("JARVIS_API_KEY") or "",
        "sdk": os.getenv("JARVIS_SDK") or "openai",
    }


def _parse_args(argv: list[str]) -> tuple[bool, bool, str, str, str, str, bool]:
    # Load .env configuration as defaults
    env_config = _load_env_config()

    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS AI Assistant - Professional AI engineering assistant",
        add_help=True
    )

    parser.add_argument(
        "--model", "-m",
        type=str,
        default=env_config["model"],
        help="Model name to use (e.g., gpt-4o, claude-3-5-sonnet-20241022)"
    )

    parser.add_argument(
        "--base_url",
        type=str,
        default=env_config["base_url"],
        help="Base URL for the LLM API (e.g., https://api.openai.com/v1)"
    )

    parser.add_argument(
        "--apikey", "--api-key",
        type=str,
        default=env_config["apikey"],
        help="API key for the LLM provider"
    )

    parser.add_argument(
        "--sdk",
        type=str,
        default=env_config["sdk"],
        choices=["openai", "anthropic"],
        help="SDK mode to use (openai or anthropic)"
    )

    parser.add_argument(
        "--cli",
        action="store_true",
        help="Launch the CLI"
    )

    parser.add_argument(
        "--tui", "--TUI",
        action="store_true",
        help="Launch the Textual UI (TUI)"
    )

    parser.add_argument(
        "--bypass", "--yolo",
        action="store_true",
        help="Bypass all tool permission checks (yolo mode)"
    )

    args = parser.parse_args(argv)

    return args.cli, args.tui, args.model, args.base_url, args.apikey, args.sdk, args.bypass


def main() -> None:
    """Entry point for the jarvis command."""
    launch_cli, launch_tui, model, base_url, apikey, sdk, bypass = _parse_args(sys.argv[1:])

    # Default to CLI if no mode specified
    if not launch_cli and not launch_tui:
        launch_cli = True

    # CLI mode always uses bypass mode for smooth tool execution
    if launch_cli and not bypass:
        bypass = True

    # Launch appropriate interface
    if launch_tui:
        from interface.textual_ui.tui_main import main as tui_main
        # TUI needs to be run synchronously (Textual handles its own event loop)
        tui_main(model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass)
    else:
        from interface.cli.cli import main as cli_main
        # CLI is now async
        import asyncio
        asyncio.run(cli_main(launch_cli=launch_cli, model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass))


if __name__ == "__main__":
    main()
