"""RPC mode entry point — reads JSONL from stdin, writes events + responses to stdout.

This module is the main loop for ``--mode rpc``.  It reads commands from
stdin one JSONL line at a time, dispatches them to ``RpcSession``, and
writes events/responses to stdout.

Usage
-----
.. code-block:: python

    # From another Python process:
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "jarvis", "--mode", "rpc",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    # Send: {"id":"1","type":"prompt","message":"Hello"}\\n
    # Read events from proc.stdout
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from jarvis.core.rpc.handler import RpcSession
from jarvis.core.rpc.types import RpcCommand, serialize

logger = logging.getLogger(__name__)


async def run_rpc_mode(
    model: str = "",
    base_url: str = "",
    apikey: str = "",
    sdk: str = "",
    bypass: bool = False,
) -> None:
    """Main RPC event loop.

    Reads JSONL lines from stdin, dispatches commands,
    writes events + responses to stdout.

    Exits when stdin closes.
    """
    session = RpcSession(
        model=model,
        base_url=base_url,
        apikey=apikey,
        sdk=sdk,
        bypass=bypass,
    )

    try:
        # Initialize the agent session
        await session.initialize()

        # Send a hello event to indicate RPC mode is ready
        sys.stdout.write(serialize({"type": "event", "event": "rpc_ready"}) + "\n")
        sys.stdout.flush()

        # Read commands from stdin line by line (using executor for blocking read)
        loop = asyncio.get_event_loop()

        while True:
            try:
                # Read one line from stdin via executor (works on all platforms)
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except Exception:
                break

            if not line:
                break  # EOF

            raw = line.strip()
            if not raw:
                continue

            try:
                data = json.loads(raw)
                cmd = RpcCommand(**data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Invalid JSONL command: %s", e)
                continue

            # Dispatch command (fire-and-forget to keep reading stdin)
            asyncio.ensure_future(session.handle_command(cmd))

        # Wait for pending commands to finish
        await asyncio.sleep(0.5)

    except Exception as e:
        logger.exception("RPC mode failed: %s", e)
        sys.stdout.write(serialize({"type": "event", "event": "rpc_error", "error": str(e)}) + "\n")
        sys.stdout.flush()
    finally:
        await session.shutdown()


def main_entry() -> None:
    """Entry point called from CLI parser with ``--mode rpc``."""
    asyncio.run(run_rpc_mode())
