"""AgentLoop wrapper for JARVIS integration."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias, cast

from core.agents.coding_agent import CodingAgent
from core.agents.manager import AgentManager
from core.agents.profiles import AgentProfile as CoreAgentProfile
from core.config.settings import Settings
from core.tools.registry import ToolRegistry
from core.rewind import RewindManager, RewindError
from core.history import ConversationHistory, create_user_message, create_assistant_message

from interface.textual_ui.types import (
    AgentStats,
    AssistantEvent,
    BaseEvent,
    LLMMessage,
    ReasoningEvent,
    Role,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)
from interface.textual_ui.tool_results import (
    BashResult,
    GrepMatch,
    GrepResult,
    ReadFileResult,
    SearchReplaceResult,
    WriteFileResult,
)


# Use the core AgentProfile directly
AgentProfile: TypeAlias = CoreAgentProfile

# Type alias for event types
Event: TypeAlias = BaseEvent | AssistantEvent | ReasoningEvent | ToolCallEvent | ToolResultEvent | UserMessageEvent

logger = logging.getLogger(__name__)


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


# ============================================================================
# Compaction System
# ============================================================================

class CompactionStrategy(Enum):
    """Compaction strategies for different modes."""
    AGGRESSIVE = "aggressive"   # Summarize more aggressively, keep fewer messages
    BALANCED = "balanced"       # Default: good balance of detail and tokens
    CONSERVATIVE = "conservative"  # Only compact when needed, keep more history


class MessageType(Enum):
    """Types of messages for prioritization during compaction."""
    SYSTEM = ("system", 8)
    USER_IMPORTANT = ("user_important", 8)      # Initial user message, task definition
    TOOL_RESULT_IMPORTANT = ("tool_result_important", 8)  # File write, test results, git ops
    ASSISTANT_PLAN = ("assistant_plan", 7)       # Agent's plan/approach
    USER_FOLLOWUP = ("user_followup", 6)         # User follow-ups
    TOOL_RESULT_NORMAL = ("tool_result_normal", 5)  # Regular tool results
    REASONING = ("reasoning", 4)                 # Thinking/reasoning blocks
    FILE_READ = ("file_read", 4)                 # Read file results (redundant content)
    GREP_RESULT = ("grep_result", 3)             # Search results (often long)
    ASSISTANT_RESPONSE = ("assistant_response", 3)  # Regular chat response
    BASH_SIMPLE = ("bash_simple", 2)             # Echo, ls, pwd
    TOOL_RESULT_TRIVIAL = ("tool_result_trivial", 1)  # Test skip, trivial output

    def __init__(self, label: str, priority: int):
        self._value_ = label
        self.priority = priority


@dataclass
class CompactionStats:
    """Statistics for compaction operations."""
    total_compactions: int = 0
    auto_compactions: int = 0
    manual_compactions: int = 0
    total_tokens_saved: int = 0
    last_compaction_time: datetime | None = None
    last_compaction_tokens_before: int = 0
    last_compaction_tokens_after: int = 0
    compaction_history: deque[tuple[datetime, str, int, int]] = field(default_factory=lambda: deque(maxlen=20))
    compaction_warnings_issued: int = 0
    compaction_errors: int = 0

    def record_compaction(self, auto: bool, tokens_before: int, tokens_after: int) -> None:
        self.total_compactions += 1
        if auto:
            self.auto_compactions += 1
        else:
            self.manual_compactions += 1
        saved = tokens_before - tokens_after
        self.total_tokens_saved += saved
        self.last_compaction_time = datetime.now()
        self.last_compaction_tokens_before = tokens_before
        self.last_compaction_tokens_after = tokens_after
        reason = "auto" if auto else "manual"
        self.compaction_history.append((datetime.now(), reason, tokens_before, tokens_after))

    def record_warning(self) -> None:
        self.compaction_warnings_issued += 1

    def record_error(self) -> None:
        self.compaction_errors += 1


@dataclass
class ContextWindowState:
    """Current state of the context window."""
    current_tokens: int = 0
    max_tokens: int = 0
    threshold_pct: float = 0.8   # Auto-compact at 80% by default
    warning_pct: float = 0.7     # Warn at 70%
    critical_pct: float = 0.9    # Critical at 90%
    messages_count: int = 0
    last_check: float = 0.0

    @property
    def usage_ratio(self) -> float:
        if self.max_tokens == 0:
            return 0.0
        return self.current_tokens / self.max_tokens

    @property
    def should_warn(self) -> bool:
        return self.usage_ratio >= self.warning_pct

    @property
    def should_auto_compact(self) -> bool:
        return self.usage_ratio >= self.threshold_pct

    @property
    def is_critical(self) -> bool:
        return self.usage_ratio >= self.critical_pct

    @property
    def status(self) -> str:
        if self.is_critical:
            return "critical"
        elif self.should_warn:
            return "warning"
        elif self.should_auto_compact:
            return "compaction_ready"
        return "ok"


@dataclass
class Stats(AgentStats):
    """Statistics tracker using JARVIS agent data."""
    steps: int = 0
    session_prompt_tokens: int = 0
    session_completion_tokens: int = 0
    session_total_llm_tokens: int = 0
    last_turn_total_tokens: int = 0
    session_cost: float = 0.0
    context_tokens: int = 0  # Current context window size
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
        """Update stats from agent using actual token counts from LLM provider."""
        p_tokens = 0
        c_tokens = 0

        # Get token usage from LLM provider
        if hasattr(agent, 'llm'):
            usage: dict[str, Any] | None = None
            # Try to get usage using get_and_clear_usage (handles both streaming and non-streaming)
            if hasattr(agent.llm, 'get_and_clear_usage'):
                get_and_clear = getattr(agent.llm, 'get_and_clear_usage', None)
                if callable(get_and_clear):
                    usage = get_and_clear()
            # Fallback: check last_token_usage directly (non-streaming)
            elif hasattr(agent.llm, 'last_token_usage'):
                usage = getattr(agent.llm, 'last_token_usage', None)

            if usage and isinstance(usage, dict):
                # Use .get() with proper type handling
                prompt_val = usage.get('prompt_tokens')
                if prompt_val is None:
                    prompt_val = usage.get('input_tokens', 0)
                p_tokens = int(prompt_val) if prompt_val is not None else 0

                completion_val = usage.get('completion_tokens')
                if completion_val is None:
                    completion_val = usage.get('output_tokens', 0)
                c_tokens = int(completion_val) if completion_val is not None else 0

        # Update stats if we have actual token counts
        if p_tokens > 0 or c_tokens > 0:
            self.prompt_tokens = p_tokens
            self.completion_tokens = c_tokens
            self.total_tokens = p_tokens + c_tokens

            # Update session totals
            self.session_prompt_tokens += p_tokens
            self.session_completion_tokens += c_tokens
            self.session_total_llm_tokens += (p_tokens + c_tokens)
            self.last_turn_total_tokens = p_tokens + c_tokens
            self.steps += 1

        # Always update context tokens for compaction tracking (handles cached token case)
        self.context_tokens = self.session_prompt_tokens


@dataclass
class HookConfigIssue:
    """Issue with hook configuration."""
    file: str
    message: str


class AgentLoop:
    """AgentLoop that wraps JARVIS's CodingAgent with enhanced core integration."""

    def __init__(
        self,
        agent: CodingAgent,
        config: Settings,
        tool_registry: ToolRegistry,
        agent_manager: AgentManager | None = None,
        disabled_tools: list[str] | None = None,
    ):
        self.agent: CodingAgent = agent
        self.config: Settings = config
        self.base_config: Settings = config
        self.tool_registry: ToolRegistry = tool_registry
        # Initialize event queue first
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        # Set event queue on tool registry for tools that need to emit events
        self.tool_registry.event_queue = self._event_queue
        # Also update all tools with the event queue
        self.tool_registry.update_tool_providers(event_queue=self._event_queue)
        self._disabled_tools: list[str] = disabled_tools or []

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
        self.hook_config_issues: list[HookConfigIssue] = []
        self.tool_manager = ToolManagerAdapter(tool_registry)
        self.session_logger = SessionLoggerAdapter()
        self.session_id: str | None = None
        self.parent_session_id: str | None = None
        # Initialize rewind manager with proper callbacks
        self.rewind_manager = RewindManager(
            messages=self.agent.memory,
            save_messages=self._save_messages,
            reset_session=self._reset_session_callback,
        )

        # ====================================================================
        # Compaction System
        # ====================================================================
        self.compaction_stats = CompactionStats()
        max_tokens_val: int = 200000
        if hasattr(config, 'max_tokens'):
            mt = config.max_tokens
            if isinstance(mt, int):
                max_tokens_val = mt
            elif isinstance(mt, (str, float)):
                try:
                    max_tokens_val = int(mt)
                except (ValueError, TypeError):
                    pass
        self.context_window = ContextWindowState(
            max_tokens=max_tokens_val
        )
        self._compaction_strategy = CompactionStrategy.BALANCED
        self._last_compaction_check: float = 0.0
        self._auto_compaction_enabled: bool = True
        self._compaction_in_progress: bool = False
        self._compaction_callback: Callable[[dict[str, Any]], None] | None = None

        # Integration with JARVIS's actual memory system
        self._approval_callback: Callable[[str, dict[str, Any], str, list[Any]], bool] | None = None
        self._user_input_callback: Callable[[str], str] | None = None
        # NOTE: _event_queue is already created at the top of __init__ (line ~284)
        # and shared with the tool registry.  Do NOT recreate it here.
        self._stream_chunks: list[str] = []
        self._reasoning_chunks: list[str] = []
        self._is_running = False
        self._tool_call_ids: dict[str, str] = {}  # Track tool call IDs
        self._disabled_tools: list[str] = []  # Track disabled tools
        self._heartbeat_running = False  # Track heartbeat subagent status
        
        # Set up tool call/result callbacks for event tracking
        self.agent.tool_call_callback = self._on_tool_call
        self.agent.tool_result_callback = self._on_tool_result
        # Set up reasoning callback to capture reasoning content
        self.agent.reasoning_callback = self._on_reasoning
        
        # Initialize heartbeat system
        self._setup_heartbeat()
        
        # Note: Heartbeat will be started when the TUI app is mounted
        # (via start_heartbeat_if_enabled method) to ensure event loop is running
        
        # ====================================================================
        # Conversation History System
        # ====================================================================
        self.history = ConversationHistory()
        self.session_id = self.history.session_id

    @property
    def messages(self) -> list[LLMMessage]:
        """Get messages from agent's memory."""
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

    async def teleport_to_vibe_code(self, prompt: str | None) -> AsyncGenerator[Event, None]:
        """Stub for teleport functionality."""
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

    async def reload_with_initial_messages(self, base_config: Settings | None = None) -> None:
        """Reload agent with initial messages."""
        self.agent.clear_memory()
        self.agent.rebuild_system_prompt()

    async def clear_history(self) -> None:
        """Clear agent history."""
        self.agent.clear_memory()

    async def compact(
        self,
        extra_instructions: str | None = None,
        auto_triggered: bool = False,
        strategy: CompactionStrategy | None = None
    ) -> dict[str, Any]:
        """
        Compact conversation history using LLM summarization.

        Args:
            extra_instructions: Additional instructions for summarization
            auto_triggered: Whether this was triggered automatically
            strategy: Compaction strategy to use

        Returns:
            Dict with compaction results: {tokens_before, tokens_after, saved, summary}
        """
        if self._compaction_in_progress:
            return {"error": "Compaction already in progress"}

        self._compaction_in_progress = True
        tokens_before = self.stats.context_tokens
        messages_before = len(self.agent.memory)

        try:
            strategy = strategy or self._compaction_strategy
            summary = await self._run_llm_summarization(extra_instructions, strategy)

            # Clear old memory and store summary
            self.agent.clear_memory()
            self.agent.add_to_memory({"content": summary})

            # Update stats
            tokens_after = self.stats.context_tokens
            self.compaction_stats.record_compaction(
                auto=auto_triggered,
                tokens_before=tokens_before,
                tokens_after=tokens_after
            )

            # Emit event if callback set
            if self._compaction_callback:
                self._compaction_callback({
                    "type": "compaction_complete",
                    "auto_triggered": auto_triggered,
                    "tokens_before": tokens_before,
                    "tokens_after": tokens_after,
                    "saved": tokens_before - tokens_after,
                    "messages_before": messages_before,
                    "summary_length": len(summary)
                })

            return {
                "success": True,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "saved": tokens_before - tokens_after,
                "summary": summary[:200] + "..." if len(summary) > 200 else summary
            }

        except Exception as e:
            self.compaction_stats.record_error()
            return {"error": str(e)}
        finally:
            self._compaction_in_progress = False

    async def _run_llm_summarization(
        self,
        extra_instructions: str | None,
        strategy: CompactionStrategy
    ) -> str:
        """Run LLM-based summarization of conversation history."""
        messages = self.messages

        if not messages:
            return "No conversation history to summarize."

        # Build summarization prompt based on strategy
        system_prompt = self._get_compaction_system_prompt(strategy)
        user_prompt = self._build_compaction_user_prompt(messages, extra_instructions)

        # Use the agent's LLM provider - use getattr to safely access the method
        llm = self.agent.llm
        create_completion = getattr(llm, 'create_chat_completion', None)
        if not callable(create_completion):
            return "LLM provider does not support create_chat_completion."

        response = await create_completion(  # type: ignore[call-arg]
            model=self.agent.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )

        # Handle the response - check for choices attribute
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
            return content if content else "Summarization failed."
        return "Summarization failed: No response from LLM."

    def _get_compaction_system_prompt(self, strategy: CompactionStrategy) -> str:
        """Get system prompt for summarization based on strategy."""
        base = """You are a conversation summarizer. Create a concise, comprehensive summary of the conversation history.

Key requirements:
- Preserve all important decisions, code changes, and task progress
- Keep technical details, file paths, and specific instructions
- Maintain user intent and agent responses
- Focus on what was accomplished and what remains to do
- Format as a clear, readable narrative"""

        if strategy == CompactionStrategy.AGGRESSIVE:
            base += "\n- Be very concise. Aim for 500-800 tokens total."
        elif strategy == CompactionStrategy.CONSERVATIVE:
            base += "\n- Be thorough. Keep more details than aggressive mode."
        else:
            base += "\n- Aim for 1000-1500 tokens."

        return base

    def _build_compaction_user_prompt(self, messages: list[LLMMessage], extra: str | None) -> str:
        """Build the user prompt for summarization."""
        # Take last N messages (or all if few)
        max_messages = 20 if self._compaction_strategy != CompactionStrategy.AGGRESSIVE else 10
        relevant_messages = messages[-max_messages:]

        msg_text = "\n\n".join(
            f"{m.role.value.upper()}: {m.content[:500]}"
            for m in relevant_messages
        )

        prompt = f"""Summarize the following conversation history:

{msg_text}

Create a comprehensive summary that captures:
1. What has been accomplished so far
2. Current state of work
3. Any pending tasks or decisions
4. Key technical details that should be preserved

{extra or ""}"""

        return prompt

    def check_auto_compaction(self) -> dict[str, Any] | None:
        """
        Check if auto-compaction should be triggered.

        Returns:
            Dict with warning info if action needed, None if OK
        """
        current_time = time.time()

        # Throttle checks to once per second
        if current_time - self._last_compaction_check < 1.0:
            return None

        self._last_compaction_check = current_time

        # Update context window state
        self.context_window.current_tokens = self.stats.context_tokens
        self.context_window.messages_count = len(self.agent.memory)

        # Check thresholds
        if self.context_window.is_critical:
            return {
                "status": "critical",
                "message": f"Context window at {self.context_window.usage_ratio:.1%} capacity. Immediate compaction recommended.",
                "action": "compact"
            }
        elif self.context_window.should_warn:
            self.compaction_stats.record_warning()
            return {
                "status": "warning",
                "message": f"Context window at {self.context_window.usage_ratio:.1%} capacity. Consider compacting soon.",
                "action": "warn"
            }

        return None

    async def maybe_auto_compact(self) -> bool:
        """
        Check and perform auto-compaction if needed.

        Returns:
            True if compaction was performed, False otherwise
        """
        if not self._auto_compaction_enabled:
            return False

        if self._compaction_in_progress:
            return False

        warning = self.check_auto_compaction()
        if warning and warning.get("status") in ("critical", "warning"):
            # Perform auto-compaction
            result = await self.compact(auto_triggered=True)
            return result.get("success", False)

        return False

    def set_compaction_strategy(self, strategy: CompactionStrategy) -> None:
        """Set the compaction strategy."""
        self._compaction_strategy = strategy

    def enable_auto_compaction(self, enabled: bool = True) -> None:
        """Enable or disable auto-compaction."""
        self._auto_compaction_enabled = enabled

    def get_compaction_stats(self) -> dict[str, Any]:
        """Get compaction statistics."""
        return {
            "total_compactions": self.compaction_stats.total_compactions,
            "auto_compactions": self.compaction_stats.auto_compactions,
            "manual_compactions": self.compaction_stats.manual_compactions,
            "total_tokens_saved": self.compaction_stats.total_tokens_saved,
            "last_compaction": self.compaction_stats.last_compaction_time,
            "context_window": {
                "current_tokens": self.context_window.current_tokens,
                "max_tokens": self.context_window.max_tokens,
                "usage_ratio": self.context_window.usage_ratio,
                "status": self.context_window.status
            }
        }

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

        # Update system prompt based on profile's system_prompt_id
        system_prompt_id = self.agent_profile.overrides.get("system_prompt_id")
        if system_prompt_id:
            from core.agents.coding_agent import CodingAgent
            new_system_prompt = CodingAgent.get_system_prompt_for_profile(system_prompt_id)
            self.agent.set_system_prompt(new_system_prompt)

        # Clear session rules when switching profiles
        self.agent.clear_session_rules()

        # Refresh system prompt if needed
        await self.refresh_system_prompt()
    
    async def inject_user_context(self, context: str) -> None:
        """Inject user context into agent."""
        self.agent.update_context("user_context", context)

    def _setup_heartbeat(self) -> None:
        """Set up heartbeat system with TUI notifications."""
        # Create notifier callback that pushes events to the event queue
        async def heartbeat_notifier(result: str) -> None:
            """Notifier callback to deliver heartbeat results in TUI."""
            if result and not result.startswith("HEARTBEAT_OK") and "skipped" not in result.lower():
                # Emit heartbeat result as an assistant message
                try:
                    self._get_event_queue().put_nowait(AssistantEvent(
                        content=f"🫀 **Heartbeat**: {result}",
                        is_heartbeat=True
                    ))
                except Exception as e:
                    logger.debug(f"Failed to queue heartbeat event: {e}")
        
        # Initialize heartbeat on the agent if enabled in config
        try:
            self.agent.initialize_heartbeat(
                config_getter=lambda: self.agent_manager.config,
                notifier=heartbeat_notifier
            )
            # Heartbeat scheduler is created but not started yet
            # It will be started when needed (e.g., on user command or background task)
            logger.info("Heartbeat system configured")
        except Exception as e:
            logger.warning(f"Failed to initialize heartbeat: {e}")
    
    async def start_heartbeat_if_enabled(self) -> None:
        """Start heartbeat if configured (call after event loop is running)."""
        # Some test agents/mocks don't implement the full heartbeat surface.
        scheduler = getattr(self.agent, "heartbeat_scheduler", None)
        if callable(scheduler):
            try:
                scheduler = scheduler()
            except Exception:
                scheduler = None

        start_heartbeat = getattr(self.agent, "start_heartbeat", None)

        if (
            scheduler
            and getattr(scheduler, "enabled", False)
            and callable(start_heartbeat)
        ):
            self._heartbeat_running = True
            try:
                await start_heartbeat()
            finally:
                self._heartbeat_running = False
    
    @property
    def is_heartbeat_running(self) -> bool:
        """Check if heartbeat subagent is currently running."""
        return self._heartbeat_running

    def _drain_event_queue(self) -> None:
        """Discard stale events before starting a new turn."""
        queue = self._get_event_queue()
        while not queue.empty():
            try:
                queue.get_nowait()
            except Exception:
                break
    
    def _get_event_queue(self) -> asyncio.Queue[Event]:
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

    def _normalize_arguments(self, arguments: dict[str, Any] | str) -> dict[str, Any]:
        """Normalize arguments to always be a dict."""
        if isinstance(arguments, str):
            try:
                import json
                return json.loads(arguments)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse arguments as JSON: {arguments[:100]}")
                return {}
        return arguments if isinstance(arguments, dict) else {}

    def _map_tool_result(self, tool_name: str, arguments: dict[str, Any], result: Any) -> Any:
        """Map raw tool output to structured result models for TUI."""
        # Normalize arguments to dict (might be JSON string from text-embedded tool calls)
        arguments = self._normalize_arguments(arguments)
        
        # If result is a ToolOutput (from core), use its inner result
        raw_result = result
        if hasattr(result, 'result'):
            raw_result = getattr(result, 'result')

        # If result is already a string but we need an object, wrap it
        if isinstance(raw_result, str):
            if tool_name == "bash":
                return BashResult(stdout=raw_result, returncode=0)
            if tool_name == "grep":
                # Convert string matches to GrepMatch objects if they follow the format
                matches = []
                for line in raw_result.splitlines():
                    parts = line.split(":", 2)
                    if len(parts) == 3:
                        matches.append(GrepMatch(file=parts[0], line=int(parts[1]) if parts[1].isdigit() else 0, content=parts[2]))
                    else:
                        matches.append(GrepMatch(file="unknown", line=0, content=line))
                return GrepResult(matches=matches)
            if tool_name in ("read", "read_file"):
                path = str(arguments.get("path") or arguments.get("filePath", ""))
                return ReadFileResult(path=path, content=raw_result)
            if tool_name in ("write", "write_file"):
                path = str(arguments.get("path") or arguments.get("filePath", ""))
                return WriteFileResult(path=path, content=raw_result, bytes_written=len(raw_result))
            if tool_name == "edit":
                # For edit, we might want to return the first diff or a summary
                path = str(arguments.get("path") or arguments.get("filePath", ""))
                return SearchReplaceResult(path=path, content=raw_result)

        # Special case for grep: list of dicts to GrepMatch objects
        if tool_name == "grep" and isinstance(raw_result, list):
            matches = []
            for m in cast(list[dict[str, Any]], raw_result):
                matches.append(GrepMatch(
                    file=str(m.get("file", "unknown")),
                    line=int(m.get("line", 0)) if str(m.get("line", "")).isdigit() else 0,
                    content=str(m.get("content", ""))
                ))
            return GrepResult(matches=matches)

        return raw_result

    def _on_tool_result(self, tool_name: str, arguments: dict[str, Any], result: Any) -> None:
        """Handle tool result event from agent."""
        # Normalize arguments to dict (might be JSON string from text-embedded tool calls)
        arguments = self._normalize_arguments(arguments)
        
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

        # Track file changes for rewind snapshots
        self._track_file_snapshot(tool_name, arguments, result)

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

    def _track_file_snapshot(self, tool_name: str, arguments: dict[str, Any], result: Any) -> None:
        """Track file snapshots for rewind functionality.
        
        Called when file-modifying tools complete successfully.
        """
        # Track files modified by write and edit tools
        if tool_name in ("write", "write_file", "edit", "str_replace_editor"):
            path = str(arguments.get("path") or arguments.get("filePath", ""))
            if path:
                try:
                    content = Path(path).read_bytes()
                    self.add_file_snapshot(path, content)
                except Exception:
                    # File might not exist or be newly created
                    pass

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

            # Check for auto-compaction if enabled
            if self._auto_compaction_enabled:
                try:
                    compaction_result = await self.maybe_auto_compact()
                    if compaction_result:
                        yield f"[Auto-compacted conversation: saved ~{self.compaction_stats.last_compaction_tokens_before - self.compaction_stats.last_compaction_tokens_after} tokens]"
                except Exception:
                    self.compaction_stats.record_error()

        finally:
            if 'task' in locals() and task and not task.done():
                task.cancel()
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

        # Create checkpoint before processing user message (for rewind functionality)
        self.rewind_manager.create_checkpoint()

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

            # Save user message to history
            user_msg = create_user_message(prompt)
            self.history.append_message(user_msg)

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

            # Save assistant response to history
            assistant_content = response or "".join(self._stream_chunks)
            if assistant_content:
                assistant_msg = create_assistant_message(assistant_content)
                self.history.append_message(assistant_msg)

            # Update stats from agent memory
            self.stats.update_from_agent(self.agent)
            self.stats.trigger_listeners()

            # Check for auto-compaction if enabled
            if self._auto_compaction_enabled:
                try:
                    compaction_result = await self.maybe_auto_compact()
                    if compaction_result:
                        yield AssistantEvent(content=f"[Auto-compacted conversation: saved ~{self.compaction_stats.last_compaction_tokens_before - self.compaction_stats.last_compaction_tokens_after} tokens]")
                except Exception as e:
                    # Log but don't fail the main task
                    self.compaction_stats.record_error()

        finally:
            if 'task' in locals() and task and not task.done():
                task.cancel()
            if 'timeout_task' in locals() and timeout_task and not timeout_task.done():
                timeout_task.cancel()
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

    async def _save_messages(self) -> None:
        """Save messages to session log."""
        # SessionLoggerAdapter doesn't have save() method yet
        # This is a placeholder for future implementation
        logger.info("Save messages called during rewind")
        pass

    def _reset_session_callback(self) -> None:
        """Reset session state after rewind."""
        # Clear any running state
        self._is_running = False
        self._stream_chunks.clear()
        self._reasoning_chunks.clear()
        # Reset stats for the new forked session
        self.stats = Stats()

    def create_checkpoint(self) -> None:
        """Create a checkpoint - convenience method."""
        if hasattr(self.rewind_manager, 'create_checkpoint'):
            self.rewind_manager.create_checkpoint()

    def add_file_snapshot(self, path: str, content: bytes | None) -> None:
        """Add a file snapshot to checkpoints - convenience method."""
        if hasattr(self.rewind_manager, 'add_snapshot'):
            from core.rewind import FileSnapshot
            snapshot = FileSnapshot(path=path, content=content)
            self.rewind_manager.add_snapshot(snapshot)


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

    def activate_skill(self, skill_name: str) -> tuple[bool, str, str | None]:
        """Activate a skill and return the core manager result."""
        return self._core_manager.activate_skill(skill_name)
    
    @staticmethod
    def build_skill_prompt(user_input: str, skill: Any) -> str:
        """Build skill prompt."""
        if skill and hasattr(skill, 'content') and skill.content:
            return f"{user_input}\n\n--- Skill Context ---\n{skill.content}"
        return user_input


class MCPRegistryAdapter:
    """Adapter for MCP Registry (Currently unsupported in JARVIS core)."""
    
    def count_loaded(self, servers: list[Any]) -> int:
        """Count loaded MCP servers."""
        return 0


class ConnectorRegistryAdapter:
    """Adapter for Connector Registry (Currently unsupported in JARVIS core)."""

    connector_count: int = 0

    def get_connector_names(self) -> list[str]:
        """Get connector names."""
        return []


class ToolManagerAdapter:
    """Adapter for JARVIS ToolRegistry."""

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    @property
    def available_tools(self) -> list[str]:
        return list(self.tool_registry.get_tools().keys())

    @property
    def registered_tools(self) -> dict[str, Any]:
        return self.tool_registry.get_tools()

    def get_tool_config(self, tool_name: str) -> dict[str, Any] | None:
        """Get tool configuration."""
        tool = self.tool_registry.get(tool_name)
        if tool:
            return {"name": tool.name, "description": tool.description}
        return None

    async def refresh_remote_tools_async(self) -> None:
        """Refresh remote tools (noop for now)."""
        pass

    async def integrate_connectors_async(self) -> None:
        """Integrate connector tools (noop for now)."""
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
