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


def _parse_args(argv: list[str]) -> tuple[bool, bool, bool, str, str, str, str, bool, str, int, int, str | None, str | None]:
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
        help="Launch the Textual UI (TUI) [default]"
    )

    parser.add_argument(
        "--webui",
        action="store_true",
        help="Launch the Web UI"
    )

    parser.add_argument(
        "--bypass", "--yolo",
        action="store_true",
        help="Bypass all tool permission checks (yolo mode)"
    )

    parser.add_argument(
        "--resume", "-r",
        nargs='?',
        const='latest',
        default=None,
        dest="resume_session",
        help="Resume a session (default: most recent). Use 'list' to show available sessions."
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["interactive", "cli", "tui", "webui", "rpc", "print"],
        default=None,
        help="Execution mode: interactive (default), cli, tui, webui, rpc, or print"
    )

    # WebUI specific arguments
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="127.0.0.1",
        help="WebUI host to bind to (use 0.0.0.0 for all devices)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5173,
        help="WebUI port (default: 5173)"
    )

    parser.add_argument(
        "--backend-port", "-b",
        type=int,
        default=8765,
        help="Backend server port (default: 8765)"
    )

    args = parser.parse_args(argv)

    return args.cli, args.tui, args.webui, args.model, args.base_url, args.apikey, args.sdk, args.bypass, args.host, args.port, args.backend_port, args.resume_session, args.mode


def main() -> None:
    """Entry point for the jarvis command."""
    launch_cli, launch_tui, launch_webui, model, base_url, apikey, sdk, bypass, webui_host, webui_port, backend_port, resume_session, mode = _parse_args(sys.argv[1:])

    # Handle --resume list to show available sessions
    if resume_session == "list":
        from core.history import ConversationHistory
        history_dir = ConversationHistory().history_dir
        if history_dir.exists():
            sessions = list(history_dir.glob("*.jsonl"))
            if sessions:
                print("Available sessions:")
                for s in sorted(sessions, key=lambda p: p.stat().st_mtime, reverse=True):
                    # Get first line to get session info
                    with open(s) as f:
                        first_line = f.readline()
                        if first_line:
                            import json
                            try:
                                msg = json.loads(first_line)
                                print(f"  {s.stem} - {msg.get('timestamp', 'unknown')[:19]}")
                            except:
                                print(f"  {s.stem}")
                        else:
                            print(f"  {s.stem}")
            else:
                print("No sessions found.")
        else:
            print("No sessions found.")
        return

    # Auto-resume latest session if -r was used without argument
    if resume_session == "latest":
        from core.history import ConversationHistory
        from pathlib import Path
        history_dir = ConversationHistory().history_dir
        if history_dir.exists():
            sessions = list(history_dir.glob("*.jsonl"))
            if sessions:
                latest = max(sessions, key=lambda p: p.stat().st_mtime)
                resume_session = latest.stem
                print(f"[info]Resuming latest session: {resume_session}[/info]")
            else:
                print("No sessions to resume.")
                resume_session = None
        else:
            print("No sessions to resume.")
            resume_session = None

    # Handle mode flag
    if mode == "rpc":
        import asyncio
        from core.rpc import run_rpc_mode
        asyncio.run(run_rpc_mode(model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass))
        return

    if mode == "print":
        launch_cli = True
        # Print mode uses CLI but outputs to stdout and exits
        # For now, falls through to CLI mode

    # Default to TUI if no mode specified
    if not launch_cli and not launch_tui and not launch_webui:
        launch_tui = True

    # CLI mode always uses bypass mode for smooth tool execution
    if launch_cli and not bypass:
        bypass = True

    # Launch appropriate interface
    if launch_tui:
        from interface.textual_ui.tui_main import main as tui_main
        # TUI needs to be run synchronously (Textual handles its own event loop)
        tui_main(model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass, resume_session=resume_session)
    elif launch_webui:
        from interface.webui.webui_main import main as webui_main
        webui_main(model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass, host=webui_host, port=webui_port, backend_port=backend_port, resume_session=resume_session)
    else:
        # CLI is now async
        import asyncio

        from interface.cli.cli import main as cli_main
        asyncio.run(cli_main(launch_cli=launch_cli, model=model, base_url=base_url, apikey=apikey, sdk=sdk, bypass=bypass, resume_session=resume_session))


if __name__ == "__main__":
    main()
