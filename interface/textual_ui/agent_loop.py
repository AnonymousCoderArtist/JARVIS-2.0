"""AgentLoop wrapper for JARVIS integration."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias, cast

from core.agents.coding_agent import CodingAgent
from core.agents.manager import AgentManager
from core.agents.profiles import AgentProfile as CoreAgentProfile
from core.config.settings import Settings
from core.tools.registry import ToolRegistry

from interface.textual_ui.types import (
    AgentStats,
    AssistantEvent,
    BaseEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from interface.textual_ui.tool_results import (
    BashResult,
    GrepResult,
    ReadFileResult,
    SearchReplaceResult,
    WriteFileResult,
)


# Use the core AgentProfile directly
AgentProfile: TypeAlias = CoreAgentProfile

# Type alias for event types
Event: TypeAlias = BaseEvent | AssistantEvent | ReasoningEvent | ToolCallEvent | ToolResultEvent | UserMessageEvent


@dataclass
class TelemetryClient:
    """Stub telemetry client."""
    def send_telemetry_event(self, event: str, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Send telemetry event."""
        pass
    
    def send_user_rating_feedback(self, rating: int = 0, comment: str | None = None, **kwargs: Any) -> None:
        """Send user rating feedback."""
        pass
    
    def send_slash_command_used(self, command: str = "", command_type: str = "", **kwargs: Any) -> None:
        """Send slash command used."""
        pass
    
    def is_active(self) -> bool:
        """Check if telemetry is active."""
        return False

    def send_user_cancelled_action(self, action: str = "", **kwargs: Any) -> None:
        """Track a user cancellation action."""
        pass

    def send_user_copied_text(self, text: str = "", **kwargs: Any) -> None:
        """Track copied text."""
        pass


@dataclass
class Stats(AgentStats):
    """Statistics tracker using JARVIS agent data."""
    steps: int = 0
    session_prompt_tokens: int = 0
    session_completion_tokens: int = 0
    session_total_llm_tokens: int = 0
    last_turn_total_tokens: int = 0
    session_cost: float = 0.0
    _listeners: dict[str, list[Callable[[Stats], None]]] = field(default_factory=dict)
    
    def add_listener(self, metric: str, callback: Callable[[Stats], None]) -> None:
        """Add listener for metric changes."""
        if metric not in self._listeners:
            self._listeners[metric] = []
        self._listeners[metric].append(callback)
    
    def trigger_listeners(self) -> None:
        """Trigger all listeners."""
        for callbacks in self._listeners.values():
            for callback in callbacks:
                try:
                    callback(self)
                except Exception:
                    pass
    
    def update_from_agent(self, agent: CodingAgent) -> None:
        """Update stats from agent memory/context."""
        # Try to get token info from agent if available
        if hasattr(agent, 'memory'):
            memory = agent.memory
            if memory:
                # Estimate tokens (rough approximation: 1 token ≈ 4 chars)
                total_chars = sum(len(str(m.get('content', ''))) for m in memory)
                self.context_tokens = total_chars // 4
        
        # Try to get token info from LLM provider if available
        if hasattr(agent, 'llm') and hasattr(agent.llm, 'last_token_usage'):
            # This is a bit dynamic as last_token_usage might not exist on all providers
            usage = getattr(agent.llm, 'last_token_usage', {})
            if isinstance(usage, dict):
                p_tokens = int(usage.get('prompt_tokens', 0))
                c_tokens = int(usage.get('completion_tokens', 0))
                self.prompt_tokens = p_tokens
                self.completion_tokens = c_tokens
                self.total_tokens = p_tokens + c_tokens
                
                # Update session totals
                self.session_prompt_tokens += p_tokens
                self.session_completion_tokens += c_tokens
                self.session_total_llm_tokens += (p_tokens + c_tokens)
                self.last_turn_total_tokens = p_tokens + c_tokens
                self.steps += 1


class AgentLoop:
    """AgentLoop that wraps JARVIS's CodingAgent with enhanced core integration."""
    
    def __init__(
        self,
        agent: CodingAgent,
        config: Settings,
        tool_registry: ToolRegistry,
        agent_manager: AgentManager | None = None,
    ):
        self.agent: CodingAgent = agent
        self.config: Settings = config
        self.base_config: Settings = config
        self.tool_registry: ToolRegistry = tool_registry

        # Use provided agent manager or create a new one
        if agent_manager is not None:
            self.agent_manager: AgentManager = agent_manager
        else:
            # Initialize agent manager with safety profiles
            self.agent_manager = AgentManager(
                config_getter=lambda: self.config,
                initial_agent="default"
            )
        self.agent_profile: CoreAgentProfile = self.agent_manager.active_profile

        # Set the config getter on the agent to use profile-applied configuration
        self.agent.set_config_getter(lambda: self.agent_manager.config)

        self.stats = Stats()
        self.telemetry_client = TelemetryClient()
        self.is_initialized = True
        self.skill_manager = SkillManagerAdapter()
        self.mcp_registry = MCPRegistryAdapter()
        self.connector_registry = ConnectorRegistryAdapter()
        self.hook_config_issues: list[str] = []
        self.tool_manager = ToolManagerAdapter(tool_registry)
        self.session_logger = SessionLoggerAdapter()
        self.session_id: str | None = None
        self.parent_session_id: str | None = None
        self.rewind_manager = RewindManagerAdapter()

        # Integration with JARVIS's actual memory system
        self._approval_callback: Callable[[str, dict[str, Any], str, list[Any]], Any] | None = None
        self._user_input_callback: Callable[[str], str] | None = None
        self._event_queue: asyncio.Queue[Event] | None = None
        self._stream_chunks: list[str] = []
        self._reasoning_chunks: list[str] = []
        self._is_running = False
        self._tool_call_ids: dict[str, str] = {}  # Track tool call IDs

        # Set up tool call/result callbacks for event tracking
        self.agent.tool_call_callback = self._on_tool_call
        self.agent.tool_result_callback = self._on_tool_result
        # Set up reasoning callback to capture reasoning content
        self.agent.reasoning_callback = self._on_reasoning
    
    @property
    def messages(self) -> list[LLMMessage]:
        """Get messages from agent's memory."""
        from interface.textual_ui.types import LLMMessage, Role
        
        # Convert agent memory to TUI LLMMessage format
        messages: list[LLMMessage] = []
        for entry in self.agent.memory:
            content = entry.get('content', '')
            response = entry.get('response', '')
            
            # Add user message
            if content:
                messages.append(LLMMessage(
                    role=Role.user,
                    content=str(content)
                ))
            
            # Add assistant response
            if response:
                messages.append(LLMMessage(
                    role=Role.assistant,
                    content=str(response)
                ))
        
        return messages

    async def teleport_to_vibe_code(self, prompt: str | None) -> AsyncGenerator[Event, TeleportPushResponseEvent | None]:
        """Stub for teleport functionality."""
        from interface.textual_ui.types import UserMessageEvent, AssistantEvent
        if prompt:
            yield UserMessageEvent(content=prompt)
        yield AssistantEvent(content="Teleport to vibe code not fully implemented in adapter.")

    def reset_messages(self, messages: list[LLMMessage]) -> None:
        """Reset agent memory with new messages."""
        self.agent.clear_memory()
        for msg in messages:
            if msg.role == Role.user:
                self.agent.add_to_memory({"content": msg.content})
            elif msg.role == Role.assistant:
                self.agent.add_to_memory({"response": msg.content})

    async def reload_with_initial_messages(self, base_config: Settings) -> None:
        """Reload agent with initial messages."""
        self.agent.clear_memory()
        self.agent.rebuild_system_prompt()

    async def clear_history(self) -> None:
        """Clear agent history."""
        self.agent.clear_memory()

    async def compact(self, extra_instructions: str | None = None) -> None:
        """Compact conversation history."""
        # Stub for compaction
        pass

    async def wait_until_ready(self) -> None:
        """Wait until agent is ready."""
        # JARVIS agent is ready immediately after initialization
        await asyncio.sleep(0)
    
    def set_approval_callback(self, callback: Callable[[str, Any, str, list[Any] | None], Any]) -> None:
        """Set approval callback for tool execution."""
        self._approval_callback = callback
        self.agent.set_approval_callback(callback)
    
    def set_user_input_callback(self, callback: Callable[[Any], Any]) -> None:
        """Set user input callback."""
        self._user_input_callback = callback
    
    def approve_always(self, tool_name: str, permissions: list[Any]) -> None:
        """Approve tool always (store in config or agent state)."""
        self.agent.approve_always(tool_name, permissions)
    
    def emit_new_session_telemetry(self) -> None:
        """Emit new session telemetry."""
        if self.telemetry_client.is_active():
            self.telemetry_client.send_telemetry_event("session_start", {
                "model": self.agent.model,
            })
    
    def refresh_config(self) -> None:
        """Refresh configuration."""
        # Reload config if needed
        pass
    
    async def refresh_system_prompt(self) -> None:
        """Refresh system prompt with current tool descriptions."""
        self.agent.rebuild_system_prompt()
    
    async def switch_agent(self, profile_name: str) -> None:
        """Switch to a different agent profile."""
        # Switch profile in agent manager
        self.agent_manager.switch_profile(profile_name)
        self.agent_profile = self.agent_manager.active_profile

        # Update the config getter to use the new profile configuration
        self.agent.set_config_getter(lambda: self.agent_manager.config)

        # Clear session rules when switching profiles
        self.agent.clear_session_rules()

        # Refresh system prompt if needed
        await self.refresh_system_prompt()
    
    async def inject_user_context(self, context: str) -> None:
        """Inject user context into agent."""
        self.agent.update_context("user_context", context)

    def _drain_event_queue(self) -> None:
        """Discard stale events before starting a new turn."""
        queue = self._get_event_queue()
        while not queue.empty():
            try:
                queue.get_nowait()
            except Exception:
                break
    
    def _get_event_queue(self) -> asyncio.Queue[Event]:
        if self._event_queue is None:
            self._event_queue = asyncio.Queue()
        return self._event_queue

    def _on_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Handle tool call event from agent."""
        # Queue tool call event for UI synchronously
        # Generate a unique tool_call_id for tracking
        import uuid
        tool_call_id = str(uuid.uuid4())
        self._tool_call_ids[tool_name] = tool_call_id
        # Try to get tool class from tool registry
        tool_class = ""
        try:
            tool = self.tool_registry.get(tool_name)
            if tool:
                tool_class = tool.__class__.__name__
        except Exception:
            pass
        
        self._get_event_queue().put_nowait(ToolCallEvent(
            tool_name=tool_name,
            tool_args=arguments,
            tool_call_id=tool_call_id,
            tool_class=tool_class
        ))

    def _map_tool_result(self, tool_name: str, arguments: dict[str, Any], result: Any) -> Any:
        """Map raw tool output to structured result models for TUI."""
        # If result is a ToolOutput (from core), use its inner result
        raw_result = result
        if hasattr(result, 'result'):
            raw_result = getattr(result, 'result')
        
        # If result is already a string but we need an object, wrap it
        if isinstance(raw_result, str):
            if tool_name == "bash":
                return BashResult(stdout=raw_result, returncode=0)
            if tool_name == "grep":
                return GrepResult(matches=raw_result)
            if tool_name in ("read", "read_file"):
                path = str(arguments.get("path") or arguments.get("filePath", ""))
                return ReadFileResult(path=path, content=raw_result)
            if tool_name in ("write", "write_file"):
                path = str(arguments.get("path") or arguments.get("filePath", ""))
                return WriteFileResult(path=path, content=raw_result, bytes_written=len(raw_result))
            if tool_name == "edit":
                # For edit, we might want to return the first diff or a summary
                return SearchReplaceResult(content=raw_result)
        
        # Special case for grep: list of dicts to formatted string
        if tool_name == "grep" and isinstance(raw_result, list):
            formatted = []
            for m in cast(list[dict[str, Any]], raw_result):
                file = str(m.get("file", "unknown"))
                line = str(m.get("line", "?"))
                content = str(m.get("content", ""))
                formatted.append(f"{file}:{line}:{content}")
            return GrepResult(matches="\n".join(formatted))
            
        return raw_result

    def _on_tool_result(self, tool_name: str, arguments: dict[str, Any], result: Any) -> None:
        """Handle tool result event from agent."""
        # Queue tool result event for UI synchronously
        # Use the same tool_call_id as the tool call
        tool_call_id = self._tool_call_ids.get(tool_name, "")
        # Try to get tool class from tool registry
        tool_class = ""
        error = ""
        try:
            tool = self.tool_registry.get(tool_name)
            if tool:
                tool_class = tool.__class__.__name__
        except Exception as e:
            error = str(e)
        
        # Determine if result indicates success or failure
        if hasattr(result, 'success') and not getattr(result, 'success'):
            if hasattr(result, 'error'):
                error = str(getattr(result, 'error'))
        
        # Map result to structured model for UI
        mapped_result = self._map_tool_result(tool_name, arguments, result)
        
        self._get_event_queue().put_nowait(ToolResultEvent(
            tool_name=tool_name,
            result=mapped_result,
            tool_call_id=tool_call_id,
            tool_class=tool_class,
            error=error,
            skipped=False,
            skip_reason="",
            cancelled=False,
            duration=0.0
        ))
        
        # Clean up the tool_call_id after use
        if tool_name in self._tool_call_ids:
            del self._tool_call_ids[tool_name]

    def _on_reasoning(self, reasoning: str) -> None:
        """Handle reasoning content from agent."""
        # Queue reasoning event for UI synchronously
        if reasoning.strip():
            self._get_event_queue().put_nowait(ReasoningEvent(content=reasoning))
        # Also store in chunks for potential direct access
        self._reasoning_chunks.append(reasoning)
    
    async def process_message(self, message: str) -> AsyncGenerator[str, None]:
        """Process a message and stream response using JARVIS agent."""
        if self._user_input_callback:
            yield message
            return
        
        self._is_running = True
        self._stream_chunks = []
        self._reasoning_chunks = []
        self._drain_event_queue()

        # We need an event queue for strings
        string_queue: asyncio.Queue[str] = asyncio.Queue()

        # Set up streaming callback
        def stream_callback(chunk: str) -> None:
            self._stream_chunks.append(chunk)
            string_queue.put_nowait(chunk)

        self.agent.stream_callback = stream_callback
        # reasoning_callback is already set in __init__ to _on_reasoning which emits events

        try:
            # Process message with JARVIS agent in a background task
            task = asyncio.create_task(self.agent.process(message))
            
            while not task.done():
                # Yield string chunks as they come in
                while not string_queue.empty():
                    yield string_queue.get_nowait()
                    
                # We also need to yield reasoning events if any show up
                # process_message yields strings, so we convert reasoning events
                while not self._get_event_queue().empty():
                    event = self._get_event_queue().get_nowait()
                    if isinstance(event, ReasoningEvent):
                        yield f"<reasoning>{event.content}</reasoning>"
                
                await asyncio.sleep(0.05)

            # Check for exception
            try:
                response = await task
            except Exception as e:
                yield f"Error processing request: {str(e)}"
                return

            # Yield any remaining stream chunks
            while not string_queue.empty():
                yield string_queue.get_nowait()
                
            # Yield any remaining reasoning
            while not self._get_event_queue().empty():
                event = self._get_event_queue().get_nowait()
                if isinstance(event, ReasoningEvent):
                    yield f"<reasoning>{event.content}</reasoning>"

            # If no stream chunks, yield the response
            if response and not self._stream_chunks:
                yield response

            # Update stats from agent memory
            self.stats.update_from_agent(self.agent)
            self.stats.trigger_listeners()

        finally:
            self._is_running = False
            self.agent.stream_callback = None

    async def act(self, prompt: str) -> AsyncGenerator[Event, None]:
        """Act on a prompt and yield events for the TUI.
        
        This is the main method the TUI uses to get agent responses.
        It yields events like ReasoningEvent, AssistantEvent, ToolCallEvent, etc.
        
        Streaming support:
        - Tool calls are emitted as ToolCallEvent via _on_tool_call callback
        - Tool results are emitted as ToolResultEvent via _on_tool_result callback
        - Reasoning/thinking is emitted as ReasoningEvent via _on_reasoning callback
        - Assistant response chunks are emitted as AssistantEvent via stream_callback
        """
        self._is_running = True
        self._stream_chunks = []
        self._reasoning_chunks = []
        self._drain_event_queue()

        # Set up streaming callback to emit assistant events
        def stream_callback(chunk: str) -> None:
            self._stream_chunks.append(chunk)
            self._get_event_queue().put_nowait(AssistantEvent(content=chunk))

        self.agent.stream_callback = stream_callback
        # reasoning_callback is already set in __init__ to _on_reasoning which queues events
        # tool_call_callback and tool_result_callback are also set in __init__

        try:
            # Yield user message event
            yield UserMessageEvent(content=prompt)

            # Process message with JARVIS agent
            # We use a background task so we can yield events while it runs
            task = asyncio.create_task(self.agent.process(prompt))
            
            # Add a timeout to prevent indefinite hanging
            timeout_task = asyncio.create_task(asyncio.sleep(120))  # 2 minute timeout
            
            # Yield events as they come in with a longer timeout
            while not task.done() and not timeout_task.done():
                try:
                    # Wait for events with a timeout
                    event = await asyncio.wait_for(self._get_event_queue().get(), timeout=0.1)
                    yield event
                except asyncio.TimeoutError:
                    # No events yet, check if task is done
                    continue

            # Cancel timeout task if still running
            if not timeout_task.done():
                timeout_task.cancel()
                try:
                    await timeout_task
                except asyncio.CancelledError:
                    pass

            # Check if we timed out
            if timeout_task.done() and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                yield AssistantEvent(content="Request timed out. Please check your API key and connection.")
                return

            # Check if task raised an exception
            try:
                response = await task
            except Exception as e:
                # Yield error event if processing fails
                import traceback
                error_msg = f"Error processing request: {str(e)}\n\n{traceback.format_exc()}"
                yield AssistantEvent(content=error_msg)
                return

            # Yield any remaining queued events (tool calls, reasoning, etc.)
            while not self._get_event_queue().empty():
                event = self._get_event_queue().get_nowait()
                yield event

            # Streaming callbacks have already yielded the assistant content. Only emit
            # the final response when the provider did not stream any text chunks.
            if response and not self._stream_chunks:
                yield AssistantEvent(content=response)
            elif not self._stream_chunks:
                # If no response and no stream chunks, yield a message
                yield AssistantEvent(content="No response generated.")

            # Update stats from agent memory
            self.stats.update_from_agent(self.agent)
            self.stats.trigger_listeners()

        finally:
            self._is_running = False
            self.agent.stream_callback = None
    
    async def run(self) -> None:
        """Run the agent loop (not used in TUI mode)."""
        pass
    
    async def get_events(self) -> AsyncGenerator[Event, None]:
        """Get events from the event queue."""
        while self._is_running:
            try:
                event = await asyncio.wait_for(self._get_event_queue().get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                continue


from core.skills.manager import SkillManager as CoreSkillManager

class SkillManagerAdapter:
    """Adapter for JARVIS SkillManager."""
    
    def __init__(self) -> None:
        self._core_manager = CoreSkillManager()
    
    @property
    def available_skills(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._core_manager.get_all_available_skills())
        
    @property
    def custom_skills_count(self) -> int:
        all_skills = self._core_manager.get_all_available_skills()
        builtin = self._core_manager.get_builtin_skills()
        return len(all_skills) - len(builtin)
    
    def parse_skill_command(self, command: str) -> Any:
        """Parse skill command."""
        if command.startswith("/skill "):
            skill_name = command.split(" ", 1)[1].strip()
            return self._core_manager.get_skill_profile(skill_name)
        return None


class MCPRegistryAdapter:
    """Adapter for MCP Registry (Currently unsupported in JARVIS core)."""
    
    def count_loaded(self, servers: list[Any]) -> int:
        """Count loaded MCP servers."""
        return 0


class ConnectorRegistryAdapter:
    """Adapter for Connector Registry (Currently unsupported in JARVIS core)."""
    
    def __init__(self) -> None:
        self.connector_count = 0


# AgentManagerAdapter removed - using real AgentManager from core.agents.manager


class ToolManagerAdapter:
    """Adapter for JARVIS ToolRegistry."""
    
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
    
    @property
    def available_tools(self) -> list[str]:
        return list(self.tool_registry.get_tools().keys())
    
    def get_tool_config(self, tool_name: str) -> dict[str, str] | None:
        """Get tool configuration."""
        tool = self.tool_registry.get(tool_name)
        if tool:
            return {"name": tool.name, "description": tool.description}
        return None
        
    async def refresh_remote_tools_async(self) -> None:
        """Refresh remote tools (noop for now)."""
        pass


class SessionLoggerAdapter:
    """Adapter for session logging."""

    def __init__(self) -> None:
        from pathlib import Path
        self.enabled = False
        self.session_id: str | None = None
        self.session_dir = Path.cwd()
        self.session_config: dict[str, Any] | None = None

    def resume_existing_session(self, session_id: str, session_path: str) -> None:
        """Resume an existing session."""
        from pathlib import Path
        self.session_id = session_id
        self.session_dir = Path(session_path).parent


class RewindManagerAdapter:
    """Adapter for session rewinding."""
    
    def has_file_changes_at(self, index: int) -> bool:
        """Check if there are file changes at a specific message index."""
        return False
    
    async def rewind_to_message(self, index: int, restore_files: bool = False) -> tuple[str, list[Any]]:
        """Rewind the session to a specific message index."""
        return "Rewind successful (stub)", []
