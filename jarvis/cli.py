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
        "model": os.getenv("JARVIS_MODEL", "gpt-4o"),
        "base_url": os.getenv("JARVIS_BASE_URL"),
        "apikey": os.getenv("JARVIS_API_KEY"),
        "sdk": os.getenv("JARVIS_SDK", "openai"),
    }


def _parse_args(argv: list[str]) -> tuple[bool, str, str, str, str, str]:
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
        choices=["openai", "anthropic", "standard"],
        help="SDK mode to use (openai, anthropic, standard)"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Launch the Rich CLI"
    )
    
    args = parser.parse_args(argv)
    return args.cli, args.model, args.base_url, args.apikey, args.sdk


def main() -> None:
    """Entry point for the jarvis command."""
    launch_cli, model, base_url, apikey, sdk = _parse_args(sys.argv[1:])
    
    # Pass provider configuration to CLI
    from interface.cli.cli import main as cli_main
    cli_main(launch_cli, model=model, base_url=base_url, apikey=apikey, sdk=sdk)


if __name__ == "__main__":
    main()
