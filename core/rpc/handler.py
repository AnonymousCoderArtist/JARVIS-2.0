"""RPC handler — receives JSONL commands on stdin, sends events + responses on stdout.

Usage
-----
Start with ``python -m jarvis --mode rpc``, then pipe JSONL commands:

.. code-block:: bash

    echo '{"id":"1","type":"prompt","message":"Hello"}' | jarvis --mode rpc
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import traceback
from pathlib import Path

from core.agents.jarvis_v2 import JarvisV2
from core.config.settings import Settings
from core.llm_sdk.openai.sdk import OpenAISDK
from core.llm_sdk.anthropic.sdk import AnthropicSDK
from core.llm.sdk_adapter import SDKAdapter
from core.rpc.types import (
    RpcCommand,
    RpcEvent,
    RpcResponse,
    make_event,
    serialize,
)
from core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_stdout_lock = asyncio.Lock()


async def write_json(obj: Any) -> None:
    """Write a JSONL line to stdout (thread-safe)."""
    line = serialize(obj)
    async with _stdout_lock:
        sys.stdout.write(line + "\n")
        await asyncio.get_event_loop().run_in_executor(None, sys.stdout.flush)


async def send_response(cmd_id: str, success: bool = True, data: Any = None, error: str | None = None) -> None:
    await write_json(RpcResponse(id=cmd_id, success=success, data=data, error=error))


async def send_event(event_type: str, **kwargs: Any) -> None:
    await write_json(make_event(event_type, **kwargs))


# ---------------------------------------------------------------------------
# RPC Session
# ---------------------------------------------------------------------------


class RpcSession:
    """Manages an agent session for the RPC lifecycle.

    One RPC process hosts one agent session at a time.
    """

    def __init__(self, model: str = "", base_url: str = "", apikey: str = "", sdk: str = "", bypass: bool = False):
        self.model = model
        self.base_url = base_url
        self.apikey = apikey
        self.sdk = sdk
        self.bypass = bypass

        self._agent: JarvisV2 | None = None
        self._config: Settings | None = None
        self._tool_registry: ToolRegistry | None = None
        self._stream_callback = None
        self._reasoning_callback = None
        self._turn_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _create_llm_provider(self):
        """Create the LLM provider from SDK settings."""
        sdk = (
            AnthropicSDK(api_key=self.apikey, base_url=self.base_url)
            if self.sdk == "anthropic"
            else OpenAISDK(api_key=self.apikey, base_url=self.base_url)
        )
        provider = SDKAdapter(sdk, "rpc-provider")
        return provider, self.model or "gpt-4o"

    async def initialize(self) -> None:
        """Create the agent, tools, and wire everything up.

        Call once before processing commands.
        """
        self._config = Settings()
        self._tool_registry = ToolRegistry()

        # Register all built-in tools
        self._register_tools()

        # Create LLM provider
        llm_provider, effective_model = self._create_llm_provider()

        # Create the agent
        self._agent = JarvisV2(
            llm_provider=llm_provider,
            tool_registry=self._tool_registry,
            model=effective_model,
            config_getter=lambda: self._config,
            bypass_tool_permissions=self.bypass,
            use_concurrent_tools=True,
        )

        # Wire streaming callbacks → RPC events
        self._agent.stream_callback = self._on_stream
        self._agent.reasoning_callback = self._on_reasoning
        self._agent.tool_call_callback = self._on_tool_call
        self._agent.tool_result_callback = self._on_tool_result
        self._agent.status_callback = self._on_status

        await send_event("session_started", content=f"Session started with model {effective_model}")

    def _register_tools(self) -> None:
        """Register standard tools."""
        from core.tools.file_tools import FileReadTool, FileWriteTool, LSTool, FindTool
        from core.tools.file_edit_tool import EditTool
        from core.tools.grep_tool import GrepSearchTool
        from core.tools.code_tools import BashTool
        from core.tools.skill_manage_tool import SkillTool

        for tool_cls in [FileReadTool, FileWriteTool, EditTool, BashTool, LSTool, FindTool, GrepSearchTool, SkillTool]:
            try:
                instance = tool_cls(
                    tool_registry=self._tool_registry,
                    llm_provider=self.llm_provider if hasattr(self, 'llm_provider') else None,
                )
                self._tool_registry.register(instance)
            except Exception as e:
                logger.warning("Failed to register tool %s: %s", tool_cls.__name__, e)

    async def shutdown(self) -> None:
        """Clean up the session."""
        if self._agent is not None:
            self._agent.clear_memory()
        await send_event("session_shutdown")

    # ------------------------------------------------------------------
    # Callbacks → RPC events
    # ------------------------------------------------------------------

    def _on_stream(self, text: str) -> None:
        """Called by the agent for every streaming text chunk."""
        asyncio.ensure_future(send_event("text_delta", delta=text))

    def _on_reasoning(self, text: str) -> None:
        """Called by the agent for reasoning content."""
        asyncio.ensure_future(send_event("thinking_delta", delta=text))

    def _on_tool_call(self, tool_name: str, tool_args: dict) -> None:
        """Called when a tool call starts."""
        asyncio.ensure_future(send_event("tool_call_start", tool_name=tool_name, tool_args=tool_args))

    def _on_tool_result(self, tool_name: str, tool_args: dict, result: any) -> None:
        """Called when a tool finishes."""
        success = getattr(result, "success", False) if result is not None else False
        error = getattr(result, "error", None) if result is not None else None
        result_val = getattr(result, "result", None) if result is not None else None
        asyncio.ensure_future(send_event("tool_call_end", tool_name=tool_name, success=success, tool_result=result_val, error=error))

    def _on_status(self, status: str) -> None:
        """Called when the agent status changes."""
        asyncio.ensure_future(send_event("status", status=status))

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def handle_command(self, cmd: RpcCommand) -> None:
        """Route a command to the appropriate handler."""
        handlers = {
            "prompt": self._handle_prompt,
            "steer": self._handle_steer,
            "follow_up": self._handle_follow_up,
            "bash": self._handle_bash,
            "compact": self._handle_compact,
            "new_session": self._handle_new_session,
            "get_state": self._handle_get_state,
            "get_messages": self._handle_get_messages,
            "get_tools": self._handle_get_tools,
            "set_model": self._handle_set_model,
        }

        handler = handlers.get(cmd.type)
        if handler is None:
            await send_response(cmd.id, success=False, error=f"Unknown command type: {cmd.type}")
            return

        try:
            await handler(cmd)
        except Exception as e:
            logger.exception("Command %s failed", cmd.type)
            await send_response(cmd.id, success=False, error=str(e))

    async def _handle_prompt(self, cmd: RpcCommand) -> None:
        """Process a user prompt and stream back events."""
        await send_event("turn_start", turn_number=self._turn_count + 1)
        self._turn_count += 1

        result = await self._agent.process(cmd.message)

        await send_event("turn_end", turn_number=self._turn_count)
        await send_response(cmd.id, success=True, data=result)

    async def _handle_steer(self, cmd: RpcCommand) -> None:
        """Steer the agent mid-turn (deliver after current tool execution)."""
        # JARVIS's process() is synchronous per call, so steer
        # would be implemented by calling process() with a follow-up message
        # For now, treat it as a prompt
        await send_event("turn_start", turn_number=self._turn_count + 1)
        self._turn_count += 1

        result = await self._agent.process(cmd.message)

        await send_event("turn_end", turn_number=self._turn_count)
        await send_response(cmd.id, success=True, data=result)

    async def _handle_follow_up(self, cmd: RpcCommand) -> None:
        """Queue a message to be processed after the current turn."""
        await send_event("turn_start", turn_number=self._turn_count + 1)
        self._turn_count += 1

        result = await self._agent.process(cmd.message)

        await send_event("turn_end", turn_number=self._turn_count)
        await send_response(cmd.id, success=True, data=result)

    async def _handle_bash(self, cmd: RpcCommand) -> None:
        """Execute a shell command directly."""
        try:
            import subprocess
            proc = await asyncio.create_subprocess_shell(
                cmd.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cmd.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()
                await send_response(cmd.id, success=False, error=f"Command timed out after {cmd.timeout}s", data={"stdout": stdout.decode(errors="replace") if stdout else "", "stderr": stderr.decode(errors="replace") if stderr else "", "exit_code": -1})
                return

            await send_response(cmd.id, success=proc.returncode == 0, data={"stdout": stdout.decode(errors="replace") if stdout else "", "stderr": stderr.decode(errors="replace") if stderr else "", "exit_code": proc.returncode})
        except Exception as e:
            await send_response(cmd.id, success=False, error=str(e))

    async def _handle_compact(self, cmd: RpcCommand) -> None:
        """Trigger session compaction."""
        # The current JarvisV2 doesn't expose compact directly,
        # but we can call rebuild_system_prompt as a close equivalent
        if self._agent:
            self._agent.rebuild_system_prompt()
        await send_response(cmd.id, success=True, data="Compact triggered")

    async def _handle_new_session(self, cmd: RpcCommand) -> None:
        """Reset the agent's memory for a fresh session."""
        if self._agent:
            self._agent.clear_memory()
        self._turn_count = 0
        await send_response(cmd.id, success=True, data="New session started")

    async def _handle_get_state(self, cmd: RpcCommand) -> None:
        """Return current session state."""
        state = {
            "model": self._agent.model if self._agent else self.model,
            "turn_count": self._turn_count,
            "memory_size": len(self._agent.memory) if self._agent else 0,
            "active_skills": list(self._tool_registry.active_skills.keys()) if self._tool_registry else [],
        }
        await send_response(cmd.id, success=True, data=state)

    async def _handle_get_messages(self, cmd: RpcCommand) -> None:
        """Return the full conversation history."""
        if self._agent:
            await send_response(cmd.id, success=True, data=self._agent.memory)
        else:
            await send_response(cmd.id, success=True, data=[])

    async def _handle_get_tools(self, cmd: RpcCommand) -> None:
        """Return the list of available tools."""
        if self._tool_registry:
            tools = self._tool_registry.list_tools()
            await send_response(cmd.id, success=True, data=tools)
        else:
            await send_response(cmd.id, success=True, data=[])

    async def _handle_set_model(self, cmd: RpcCommand) -> None:
        """Change the active model."""
        if cmd.model and self._agent:
            self._agent.model = cmd.model
            await send_response(cmd.id, success=True, data=f"Model changed to {cmd.model}")
        else:
            await send_response(cmd.id, success=False, error="No model specified or agent not initialized")
