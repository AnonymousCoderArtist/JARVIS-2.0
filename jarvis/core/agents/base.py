"""Base agent architecture"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias, cast

from jarvis.core.config.settings import Settings
from jarvis.core.events import (
    AgentEnded,
    AgentError,
    AgentStarted,
    EventBus,
    HookContext,
    HookRegistry,
    HookResult,
    HookStage,
    ProgressUpdated,
    StatusUpdated,
)
from jarvis.core.history import ConversationHistory
from jarvis.core.llm.base import BaseLLMProvider, MessageDict
from jarvis.core.llm_sdk.base.sdk import ToolCall
from jarvis.core.llm_sdk.tool_parser import (
    extract_text_and_tool_calls,
    has_text_tool_calls,
    normalize_tool_calls,
)
from jarvis.core.tools.permissions import (
    ApprovedRule,
    PermissionContext,
    PermissionScope,
    ToolPermission,
)
from jarvis.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Type aliases for messages and tool definitions
# MessageDict and ToolDefDict are imported from jarvis.core.llm.base

# Type aliases for callbacks
StreamCallback: TypeAlias = Callable[[str], None]
ToolCallCallback: TypeAlias = Callable[[str, dict[str, Any]], None]
ToolResultCallback: TypeAlias = Callable[[str, dict[str, Any], Any], None]
ToolStreamCallback: TypeAlias = Callable[[str, str], None]
ReasoningCallback: TypeAlias = Callable[[str], None]
ReasoningDoneCallback: TypeAlias = Callable[[], None]
ApprovalCallback: TypeAlias = Callable[[str, dict[str, Any], str, list[Any]], Any]
UserInputCallback: TypeAlias = Callable[[dict[str, Any]], Any]
ConfigGetter: TypeAlias = Callable[[], Settings]
ProgressCallback: TypeAlias = Callable[[str, float], None]
StatusCallback: TypeAlias = Callable[[str], None]


class ApprovalResponse(str, Enum):
    """Response types for tool approval"""
    YES = "yes"
    NO = "no"

    def __str__(self) -> str:
        return self.value


@dataclass
class ToolDecision:
    """Decision about tool execution"""
    verdict: str  # "execute" or "skip"
    approval_type: ToolPermission
    feedback: str | None = None
    updated_args: dict[str, Any] | None = None  # Updated args with user input


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        system_prompt: str,
        model: str | None = None,
        config_getter: ConfigGetter | None = None,
        bypass_tool_permissions: bool = False,
        use_concurrent_tools: bool = True,
        auto_discover_context: bool = True,
        event_bus: EventBus | None = None,
        hook_registry: HookRegistry | None = None,
    ):
        self.llm: BaseLLMProvider = llm_provider
        self.tools: ToolRegistry = tool_registry
        self.base_system_prompt: str = system_prompt
        self.system_prompt: str = ""
        self.model: str = model or "gpt-4"  # Use provided model or default
        self.memory: list[MessageDict] = []
        self.context: dict[str, Any] = {}
        # Per-task execution trace (used for self-evolving skills).
        # This is reset at the start of each top-level `process()` implementation.
        self.execution_trace: list[dict[str, Any]] = []
        self.current_task_input: str | None = None
        # Callbacks for streaming and tool calls
        self.stream_callback: StreamCallback | None = None
        self.tool_call_callback: ToolCallCallback | None = None
        self.tool_result_callback: ToolResultCallback | None = None
        self.tool_stream_callback: ToolStreamCallback | None = None
        self.reasoning_callback: ReasoningCallback | None = None
        self.reasoning_done_callback: ReasoningDoneCallback | None = None

        # Progress and status callbacks for async operations
        self.progress_callback: ProgressCallback | None = None
        self.status_callback: StatusCallback | None = None

        # Async configuration
        self.use_concurrent_tools: bool = use_concurrent_tools

        # Background task manager (initialized lazily)
        self._background_task_manager = None

        # Permission system
        self.approval_callback: ApprovalCallback | None = None
        self.user_input_callback: UserInputCallback | None = None
        self._session_rules: list[ApprovedRule] = []
        self._config_getter: ConfigGetter = config_getter or (lambda: Settings())
        self.bypass_tool_permissions: bool = bypass_tool_permissions

        # Conversation history (persistent, role-based)
        self.history: ConversationHistory | None = None

        # --- Event system ---
        self.event_bus: EventBus = event_bus or EventBus()
        self.hook_registry: HookRegistry = hook_registry or HookRegistry()
        # Wire the event bus into the tool registry so tool execution
        # events are automatically emitted.
        self.tools.event_bus = self.event_bus

        # Auto-discovery of project context files (JARVIS v2 mode)
        self._auto_discover_context: bool = auto_discover_context
        if auto_discover_context:
            # Rebuild the base system prompt at runtime with discovered context files
            # This must happen before _build_system_prompt() is called
            from jarvis.core.agents.system_prompts import (
                build_jarvis_v2_system_prompt,
                discover_context_files,
            )
            context_files = discover_context_files()
            self.base_system_prompt = build_jarvis_v2_system_prompt(
                context_files=context_files,
                auto_discover=False,  # prevent re-discovery inside builder
            )
        else:
            self.base_system_prompt = system_prompt

        # Dynamically build full system prompt with tool descriptions
        self._build_system_prompt()

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    async def _emit(self, event: Any) -> None:
        """Emit an event via the event bus (best-effort)."""
        try:
            await self.event_bus.emit(event)
        except Exception:
            logger.exception("Failed to emit event %s", type(event).__name__)

    async def _run_hooks(
        self, stage: HookStage, ctx: HookContext | None = None
    ) -> HookResult:
        """Run lifecycle hooks for *stage* (best-effort)."""
        try:
            return await self.hook_registry.run(stage, ctx)
        except Exception:
            logger.exception("Hook stage %s failed", stage.value)
            return HookResult(proceed=True)

    def _build_system_prompt(self) -> None:
        """Build the full system prompt with dynamic context sections.

        Tool descriptions are NOT injected here — they are sent to the model
        via the native tool calling API (tools parameter), which already
        provides names, descriptions, and schemas to the model.

        This method now also injects:
        - Discovered ``AGENTS.md`` / ``CLAUDE.md`` context files
        - System context (working directory, etc.)
        - Progressive skill descriptions (name + when_to_use)
        - Active skill full content
        """
        from jarvis.core.agents.prompts.constants import get_system_context
        from jarvis.core.resources import discover_all, read_context_files
        system_context = get_system_context()

        full_prompt = self.base_system_prompt

        # Run BEFORE_SYSTEM_PROMPT hooks (sync-compatible)
        # Note: These are run best-effort; async hooks will run on next async call
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, run hooks properly
                asyncio.ensure_future(self._run_hooks(HookStage.BEFORE_SYSTEM_PROMPT, HookContext(
                    agent_name=getattr(self, "name", ""),
                    system_prompt=full_prompt,
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                )))
        except Exception:
            pass

        # --- Discovered context files (AGENTS.md, CLAUDE.md, etc.) ---
        try:
            project_dir = getattr(self, "_config_getter", lambda: None)()
            cwd = getattr(project_dir, "cwd", None) if project_dir else None
            resources = discover_all(project_dir=cwd)
            ctx_content = read_context_files(resources.context_files)
            if ctx_content:
                full_prompt += f"\n\n---\n\n## Project Context Files\n\n{ctx_content}"
        except Exception:
            logger.debug("Failed to discover context files", exc_info=True)

        # --- System context ---
        if system_context:
            full_prompt = f"{full_prompt}\n\n---\n\n{system_context}"

        # --- Active skills (full content, loaded via activate_skill tool) ---
        if hasattr(self.tools, 'active_skills') and self.tools.active_skills:
            skills_section = "\n\n---\n\n## Active Skills\n\n"
            active_skills = cast(dict[str, str], self.tools.active_skills)
            for skill_name, skill_content in active_skills.items():
                skills_section += f"### {skill_name}\n{skill_content}\n\n"
            full_prompt += skills_section

        # --- Available skill descriptions (progressive disclosure, no full content) ---
        try:
            from jarvis.core.skills import SkillManager
            skill_manager = SkillManager()
            available_skills = skill_manager.get_skill_descriptions_for_prompt()
            if available_skills:
                full_prompt += "\n\n---\n\n" + available_skills
        except Exception:
            pass

        self.system_prompt = full_prompt

        # Run AFTER_SYSTEM_PROMPT hooks (best-effort, async)
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._run_hooks(HookStage.AFTER_SYSTEM_PROMPT, HookContext(
                    agent_name=getattr(self, "name", ""),
                    system_prompt=full_prompt,
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                )))
        except Exception:
            pass

    def rebuild_system_prompt(self) -> None:
        """Rebuild the system prompt with current tool descriptions and active skills.

        Call this after modifying the tool registry or activating skills to update the agent's
        system prompt with the latest tool descriptions and skill content.
        """
        self._build_system_prompt()

    @abstractmethod
    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a user input and generate a response

        Args:
            input: User input string
            context: Optional context dictionary

        Returns:
            Agent response string
        """
        pass

    @abstractmethod
    async def plan(self, task: str) -> list[dict[str, Any]]:
        """
        Plan the execution of a task

        Args:
            task: Task description

        Returns:
            List of action steps
        """
        pass

    def add_to_memory(self, entry: MessageDict) -> None:
        """
        Add an entry to agent memory

        Args:
            entry: Dictionary with message data (role, content, tool_calls, tool_call_id)
        """
        self.memory.append(entry)

    def get_role_memory(self) -> list[MessageDict]:
        """Get all role-based messages from memory.

        Filters memory entries that have a "role" key and returns them
        as properly formatted message dicts for LLM consumption.
        This replaces the old summary-string approach.

        Returns:
            List of message dicts with role, content, tool_calls, tool_call_id
        """
        role_entries: list[MessageDict] = [e for e in self.memory if "role" in e]
        result: list[MessageDict] = []
        for entry in role_entries:
            d: MessageDict = {"role": entry["role"], "content": entry.get("content", "")}
            if entry.get("tool_calls"):
                d["tool_calls"] = entry["tool_calls"]
            if entry.get("tool_call_id"):
                d["tool_call_id"] = entry["tool_call_id"]
            result.append(d)
        return result

    def add_role_message(
        self,
        role: str,
        content: str = "",
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        """Add a proper role-based message to memory.

        Args:
            role: Message role (user, assistant, tool, system)
            content: Message content
            tool_calls: Tool calls for assistant messages
            tool_call_id: Tool call ID for tool messages
        """
        entry: MessageDict = {"role": role}
        if content:
            entry["content"] = content
        if tool_calls:
            entry["tool_calls"] = tool_calls
        if tool_call_id:
            entry["tool_call_id"] = tool_call_id
        self.memory.append(entry)

    def update_context(self, key: str, value: Any) -> None:
        """
        Update the agent's context

        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Get a value from context

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            Context value or default
        """
        return self.context.get(key, default)

    def clear_memory(self) -> None:
        """Clear agent memory"""
        self.memory = []

    def set_approval_callback(self, callback: ApprovalCallback) -> None:
        """
        Set the callback for tool approval

        Args:
            callback: Function to call for approval (tool_name, args, tool_call_id, required_permissions) -> (ApprovalResponse, feedback)
        """
        self.approval_callback = callback

    def set_user_input_callback(self, callback: UserInputCallback) -> None:
        """
        Set the callback for user input requests (e.g., AskUserQuestion tool)

        Args:
            callback: Function to call for user input (tool_args) -> user input result
        """
        self.user_input_callback = callback

    def add_session_rule(self, rule: ApprovedRule) -> None:
        """
        Add a session-level permission rule

        Args:
            rule: ApprovedRule instance
        """
        self._session_rules.append(rule)

    def clear_session_rules(self) -> None:
        """Clear all session-level rules"""
        self._session_rules.clear()

    def set_config_getter(self, config_getter: ConfigGetter) -> None:
        """
        Set the configuration getter function

        Args:
            config_getter: Function that returns the current Settings
        """
        self._config_getter = config_getter

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """
        Set the callback for progress updates

        Args:
            callback: Function to call for progress updates (stage, progress)
        """
        self.progress_callback = callback

    def set_status_callback(self, callback: StatusCallback) -> None:
        """
        Set the callback for status updates

        Args:
            callback: Function to call for status updates (status_message)
        """
        self.status_callback = callback

    async def _should_execute_tool(
        self, tool_name: str, tool_args: dict[str, Any], tool_call_id: str
    ) -> ToolDecision:
        """
        Check if a tool should be executed based on permissions

        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments
            tool_call_id: Unique ID for this tool call

        Returns:
            ToolDecision with verdict and approval type
        """
        # Special handling for AskUserQuestion tool - get user input before execution
        if tool_name == "AskUserQuestion" and self.user_input_callback:
            try:
                user_input_result = await self.user_input_callback(tool_args)

                # Check if user cancelled
                if hasattr(user_input_result, 'cancelled') and user_input_result.cancelled:
                    return ToolDecision(
                        verdict="skip",
                        approval_type=ToolPermission.ASK,
                        feedback="User declined to answer questions",
                    )

                # Convert answers list to dict format expected by the tool
                # The tool expects: dict[str, str] where key is question text and value is answer
                answers_dict = {}
                annotations_dict = {}

                if hasattr(user_input_result, 'answers') and user_input_result.answers:
                    for answer in user_input_result.answers:
                        if hasattr(answer, 'question') and hasattr(answer, 'answer'):
                            answers_dict[answer.question] = answer.answer
                elif isinstance(user_input_result, dict) and 'answers' in user_input_result:
                    # Handle dict format
                    answers_list = user_input_result.get('answers', [])
                    for answer in answers_list:
                        if isinstance(answer, dict):
                            q = answer.get('question', '')
                            a = answer.get('answer', '')
                            if q and a:
                                answers_dict[q] = a

                # Update tool_args with the converted answers
                tool_args = tool_args.copy()
                tool_args['answers'] = answers_dict

                # Return decision to execute with updated args
                return ToolDecision(
                    verdict="execute",
                    approval_type=ToolPermission.ALWAYS,
                    updated_args=tool_args,
                )
            except Exception as e:
                # If user input fails, skip tool execution
                return ToolDecision(
                    verdict="skip",
                    approval_type=ToolPermission.ASK,
                    feedback=f"User input failed: {str(e)}",
                )

        # Get permission context from tool
        tool = self.tools.get(tool_name)
        ctx = None
        if tool and hasattr(tool, "resolve_permission"):
            ctx = tool.resolve_permission(tool_args)

        if ctx is None:
            # Default to ASK if tool doesn't implement permission checking or returns None
            ctx = PermissionContext(permission=ToolPermission.ASK)

        # Check configuration for tool-level permission
        config = self._config_getter()

        # Check bypass from instance attribute first, then config
        bypass = self.bypass_tool_permissions or config.bypass_tool_permissions
        tools_config = config.tools

        if bypass:
            return ToolDecision(
                verdict="execute",
                approval_type=ToolPermission.ALWAYS,
            )

        # Check tool-level permission from config
        tool_config = tools_config.get(tool_name, {})
        if isinstance(tool_config, dict):
            raw_perm = tool_config.get("permission", "ask")
            tool_perm = ToolPermission(raw_perm)
        else:
            tool_perm = ToolPermission.ASK

        if tool_perm == ToolPermission.ALWAYS:
            return ToolDecision(
                verdict="execute",
                approval_type=ToolPermission.ALWAYS,
            )

        if tool_perm == ToolPermission.NEVER:
            return ToolDecision(
                verdict="skip",
                approval_type=ToolPermission.NEVER,
                feedback=f"Tool '{tool_name}' is permanently disabled",
            )

        # Check session rules
        if ctx.required_permissions:
            uncovered = [
                rp
                for rp in ctx.required_permissions
                if not self._is_permission_covered(tool_name, rp)
            ]
            if not uncovered:
                return ToolDecision(
                    verdict="execute",
                    approval_type=ToolPermission.ALWAYS,
                )
        else:
            if self._is_tool_session_approved(tool_name):
                return ToolDecision(
                    verdict="execute",
                    approval_type=ToolPermission.ALWAYS,
                )
            uncovered = []

        # Ask for approval
        return await self._ask_approval(tool_name, tool_args, tool_call_id, uncovered)

    def _is_permission_covered(self, tool_name: str, required_permission: Any) -> bool:
        """
        Check if a required permission is covered by session rules

        Args:
            tool_name: Name of the tool
            required_permission: RequiredPermission instance

        Returns:
            True if covered, False otherwise
        """
        from jarvis.core.tools.utils import wildcard_match

        return any(
            rule.tool_name == tool_name
            and rule.scope == required_permission.scope
            and wildcard_match(
                required_permission.invocation_pattern, rule.session_pattern
            )
            for rule in self._session_rules
        )

    def _is_tool_session_approved(self, tool_name: str) -> bool:
        """Check whether a tool was approved for this session without granular permissions."""
        return any(
            rule.tool_name == tool_name
            and rule.scope == PermissionScope.COMMAND_PATTERN
            and rule.session_pattern == "*"
            for rule in self._session_rules
        )

    async def _ask_approval(
        self, tool_name: str, tool_args: dict[str, Any], tool_call_id: str, required_permissions: list[Any]
    ) -> ToolDecision:
        """
        Ask user for approval via callback

        Args:
            tool_name: Name of the tool
            tool_args: Tool arguments
            tool_call_id: Unique ID for this tool call
            required_permissions: List of required permissions

        Returns:
            ToolDecision with verdict
        """
        if not self.approval_callback:
            return ToolDecision(
                verdict="skip",
                approval_type=ToolPermission.ASK,
                feedback="Tool execution not permitted (no approval callback set)",
            )

        try:
            result = await self.approval_callback(
                tool_name, tool_args, tool_call_id, required_permissions
            )

            if isinstance(result, tuple) and len(result) == 2:
                response, feedback = result
            else:
                response, feedback = result, ""

            if response == "yes" or response == ApprovalResponse.YES:
                return ToolDecision(
                    verdict="execute",
                    approval_type=ToolPermission.ASK,
                )
            else:
                return ToolDecision(
                    verdict="skip",
                    approval_type=ToolPermission.ASK,
                    feedback=feedback or "Tool execution rejected by user",
                )
        except Exception as e:
            logger.error(f"Approval callback failed: {e}")
            return ToolDecision(
                verdict="skip",
                approval_type=ToolPermission.ASK,
                feedback=f"Approval check failed: {str(e)}",
            )

    def approve_always(
        self, tool_name: str, required_permissions: list[Any], save_permanently: bool = False
    ) -> None:
        """
        Handle 'Allow Always' approval

        Args:
            tool_name: Name of the tool
            required_permissions: List of required permissions
            save_permanently: Whether to save permanently to config
        """
        if required_permissions:
            # Add session rules for each required permission
            for rp in required_permissions:
                self.add_session_rule(
                    ApprovedRule(
                        tool_name=tool_name,
                        scope=rp.scope,
                        session_pattern=rp.session_pattern,
                    )
                )
        else:
            # Add a session-level allow rule for the whole tool
            self.add_session_rule(
                ApprovedRule(
                    tool_name=tool_name,
                    scope=PermissionScope.COMMAND_PATTERN,
                    session_pattern="*",
                )
            )

            # Optionally persist the tool-level permission
            if save_permanently:
                config = Settings()
                config_data = config.model_dump()
                if "tools" not in config_data:
                    config_data["tools"] = {}
                if tool_name not in config_data["tools"]:
                    config_data["tools"][tool_name] = {}

                config_data["tools"][tool_name]["permission"] = "always"
                # Need to update config back - ideally Settings should have a better way
                config.set("tools", tool_name, {"permission": "always"})
                config.save()

    def _build_messages(self, user_content: str, include_memory: bool = True) -> list[MessageDict]:
        """
        Build message list with system, user, and full conversation history.

        Loads ALL role-based messages from memory with proper roles (not just
        the last 5 entries). Use include_memory=False for sub-agents that
        should not inherit the main agent's conversation history.

        Args:
            user_content: User input content
            include_memory: Whether to include previous conversation history

        Returns:
            List of message dictionaries with proper roles
        """
        messages: list[MessageDict] = [
            {"role": "system", "content": self.system_prompt}
        ]

        if include_memory:
            # Add ALL role-based messages from memory with proper roles
            role_messages = self.get_role_memory()
            messages.extend(role_messages)

        # Add user message
        messages.append({"role": "user", "content": user_content})

        return messages

    def _drain_and_inject_notifications(
        self, messages: list[MessageDict]
    ) -> list[MessageDict]:
        """Drain pending subagent notifications and inject them as a user message.

        This is called at the start of each agent loop iteration. Any pending
        notifications from completed/failed background agents are formatted as
        XML and appended to the message history so the LLM sees them automatically.

        Progress updates are excluded — they are UI-only, matching OpenClaude's design.

        Args:
            messages: Current message history

        Returns:
            Updated message history with notification context appended
        """
        from jarvis.core.agents.notification_queue import (
            NotificationMode,
            format_notifications_for_llm,
            get_notification_queue,
        )

        queue = get_notification_queue()
        notifications = queue.drain(
            agent_id="",
            exclude_modes={NotificationMode.PROGRESS_UPDATE},
        )

        if not notifications:
            return messages

        notification_text = format_notifications_for_llm(notifications)
        if notification_text:
            messages = messages.copy()
            messages.append({"role": "user", "content": notification_text})

        return messages

    async def _process_with_tools(
        self,
        messages: list[MessageDict],
        stream: bool = False
    ) -> str:
        """
        Process messages with tool calling support using standard message roles

        This implements the agentic loop pattern:
        1. Call LLM with conversation history (system, user, assistant roles)
        2. If tool calls, execute them and add results to history
        3. Repeat until LLM returns no tool calls
        4. Return final response

        Before each LLM call, pending subagent notifications are drained and
        injected as user messages so the LLM sees them automatically.

        Args:
            messages: Message history with proper roles
            stream: Whether to stream the response

        Returns:
            Final response after tool execution
        """
        tool_definitions = self.tools.get_function_definitions()
        updated_messages = messages.copy()

        # Run BEFORE_PROMPT_BUILD hooks
        prompt_ctx = HookContext(
            agent_name=getattr(self, "name", ""),
            session_id=getattr(self, "session_id", ""),
            model=self.model,
            cwd=str(Path.cwd()),
            messages=list(updated_messages),
        )
        prompt_result = await self._run_hooks(HookStage.BEFORE_PROMPT_BUILD, prompt_ctx)
        if prompt_result.block:
            return f"Prompt build blocked by hook: {prompt_result.reason}"
        if prompt_result.inject:
            # Inject content as a user message
            updated_messages.append({"role": "user", "content": prompt_result.inject})

        while True:
            # Run BEFORE_TURN hooks
            turn_ctx = HookContext(
                agent_name=getattr(self, "name", ""),
                session_id=getattr(self, "session_id", ""),
                model=self.model,
                cwd=str(Path.cwd()),
                messages=list(updated_messages),
            )
            turn_result = await self._run_hooks(HookStage.BEFORE_TURN, turn_ctx)
            if turn_result.block:
                return f"Turn blocked by hook: {turn_result.reason}"

            # Drain pending subagent notifications and inject as context
            updated_messages = self._drain_and_inject_notifications(updated_messages)

            # Always try streaming when stream_callback is set (TUI mode)
            # This ensures real-time updates in the TUI
            if self.stream_callback:
                full_response = ""
                reasoning_content = ""
                tool_calls: list[ToolCall] = []
                try:
                    stream_result = cast(
                        AsyncGenerator[Any, None],
                        await self.llm.generate_with_tools(
                            messages=updated_messages,
                            tools=tool_definitions,
                            model=self.model,
                            stream=True,
                        ),
                    )
                    async for chunk in stream_result:
                        if isinstance(chunk, dict):
                            if chunk["type"] == "text":
                                chunk_content = cast(str, chunk["content"])
                                full_response += chunk_content
                                self.stream_callback(chunk_content)
                            elif chunk["type"] == "reasoning":
                                chunk_reasoning = cast(str, chunk["content"])
                                reasoning_content += chunk_reasoning
                                # Call reasoning callback if set and content exists
                                if chunk_reasoning and chunk_reasoning.strip():
                                    if self.reasoning_callback:
                                        self.reasoning_callback(chunk_reasoning)
                            elif chunk["type"] == "thinking":
                                # Periodic thinking indicator for models without native reasoning
                                chunk_thinking = cast(str, chunk["content"])
                                if self.reasoning_callback:
                                    self.reasoning_callback(chunk_thinking)
                            elif chunk["type"] == "tool_calls":
                                for tc in chunk.get("tool_calls", []):
                                    if hasattr(tc, "name"):
                                        # Already a ToolCall object
                                        tool_calls.append(tc)
                                    elif isinstance(tc, dict):
                                        tool_calls.append(ToolCall(
                                            id=tc.get("id", ""),
                                            name=tc.get("name", ""),
                                            arguments=tc.get("arguments", "")
                                        ))
                            elif chunk["type"] == "tool_call":
                                tool_calls.append(cast(ToolCall, chunk["tool_call"]))
                        else:
                            # Backward compatibility for string chunks
                            chunk_text = str(chunk)
                            full_response += chunk_text
                            self.stream_callback(chunk_text)

                    # Deduplicate tool calls by ID (streaming may emit both individual and batch)
                    seen_ids: set[str] = set()
                    deduped: list[ToolCall] = []
                    for tc in tool_calls:
                        if tc.id and tc.id not in seen_ids:
                            seen_ids.add(tc.id)
                            deduped.append(tc)
                        elif not tc.id:
                            deduped.append(tc)
                    tool_calls = deduped

                    # If tool calls were encountered, execute them
                    if tool_calls:
                        response_dict: dict[str, Any] = {
                            "content": full_response,
                            "tool_calls": [{"function": {"name": tc.name, "arguments": tc.arguments}, "id": tc.id} for tc in tool_calls]
                        }
                        updated_messages = await self._execute_tools_and_update_messages(
                            response_dict,
                            updated_messages,
                            use_concurrent=self.use_concurrent_tools
                        )
                        await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                            agent_name=getattr(self, "name", ""),
                            session_id=getattr(self, "session_id", ""),
                            model=self.model,
                            cwd=str(Path.cwd()),
                            messages=list(updated_messages),
                        ))
                        continue  # Loop again with updated messages

                    # Check for text-embedded tool calls ONLY when no structured tool calls were found
                    elif has_text_tool_calls(full_response):
                        cleaned_text, text_tool_calls = extract_text_and_tool_calls(full_response)
                        if text_tool_calls:
                            normalized_calls = normalize_tool_calls(text_tool_calls)
                            response_dict: dict[str, Any] = {
                                "content": cleaned_text,
                                "tool_calls": [{"function": {"name": tc["name"], "arguments": tc["arguments"]}, "id": f"text_tool_{i}"} for i, tc in enumerate(normalized_calls)]
                            }
                            updated_messages = await self._execute_tools_and_update_messages(
                                response_dict,
                                updated_messages,
                                use_concurrent=self.use_concurrent_tools
                            )
                            await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                                agent_name=getattr(self, "name", ""),
                                session_id=getattr(self, "session_id", ""),
                                model=self.model,
                                cwd=str(Path.cwd()),
                                messages=list(updated_messages),
                            ))
                            continue

                    # Signal that reasoning is done
                    if self.reasoning_done_callback:
                        self.reasoning_done_callback()
                    await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                        agent_name=getattr(self, "name", ""),
                        agent_output=full_response,
                        session_id=getattr(self, "session_id", ""),
                        model=self.model,
                        cwd=str(Path.cwd()),
                        messages=list(updated_messages),
                    ))
                    await self._run_hooks(HookStage.AFTER_PROMPT_BUILD, HookContext(
                        agent_name=getattr(self, "name", ""),
                        agent_output=full_response,
                        session_id=getattr(self, "session_id", ""),
                        model=self.model,
                        cwd=str(Path.cwd()),
                        messages=list(updated_messages),
                    ))
                    return full_response
                except Exception as e:
                    logger.warning(f"Streaming with tools failed, falling back to non-streaming: {e}")

            # Non-streaming fallback (only if stream_callback is not set or streaming failed)
            try:
                raw_response = await self.llm.generate_with_tools(
                    messages=updated_messages,
                    tools=tool_definitions,
                    model=self.model,
                )
            except Exception as e:
                logger.warning(
                    "Tool-capable generation failed; falling back to plain generation: %s",
                    e,
                )
                result = await self._process_without_tools(updated_messages, stream=stream)
                await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                    agent_name=getattr(self, "name", ""),
                    agent_output=result,
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                    messages=list(updated_messages),
                ))
                await self._run_hooks(HookStage.AFTER_PROMPT_BUILD, HookContext(
                    agent_name=getattr(self, "name", ""),
                    agent_output=result,
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                    messages=list(updated_messages),
                ))
                return result

            # Handle response
            response: MessageDict = cast(MessageDict, raw_response)

            content = str(response.get("content", ""))
            reasoning = str(response.get("reasoning_content", "") or response.get("reasoning", ""))

            # Handle reasoning content in non-streaming mode
            if reasoning and reasoning.strip() and self.reasoning_callback:
                self.reasoning_callback(reasoning)
            if self.reasoning_done_callback:
                self.reasoning_done_callback()

            # Always emit content via stream_callback if set, even in non-streaming mode
            if self.stream_callback and content:
                self.stream_callback(content)

            if response.get("tool_calls"):
                updated_messages = await self._execute_tools_and_update_messages(
                    response,
                    updated_messages,
                    use_concurrent=self.use_concurrent_tools
                )
                await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                    agent_name=getattr(self, "name", ""),
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                    messages=list(updated_messages),
                ))
                continue  # Loop again with updated messages

            # Check for text-embedded tool calls ONLY when no structured tool calls were found
            elif has_text_tool_calls(content):
                cleaned_text, text_tool_calls = extract_text_and_tool_calls(content)
                if text_tool_calls:
                    normalized_calls = normalize_tool_calls(text_tool_calls)
                    # Update the response with cleaned content and text tool calls
                    response["content"] = cleaned_text
                    response["tool_calls"] = [{"function": {"name": tc["name"], "arguments": tc["arguments"]}, "id": f"text_tool_{i}"} for i, tc in enumerate(normalized_calls)]
                    updated_messages = await self._execute_tools_and_update_messages(
                        response,
                        updated_messages,
                        use_concurrent=self.use_concurrent_tools
                    )
                    await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                        agent_name=getattr(self, "name", ""),
                        session_id=getattr(self, "session_id", ""),
                        model=self.model,
                        cwd=str(Path.cwd()),
                        messages=list(updated_messages),
                    ))
                    continue

            await self._run_hooks(HookStage.AFTER_TURN, HookContext(
                agent_name=getattr(self, "name", ""),
                agent_output=content,
                session_id=getattr(self, "session_id", ""),
                model=self.model,
                cwd=str(Path.cwd()),
                messages=list(updated_messages),
            ))

            # Run AFTER_PROMPT_BUILD hooks (once, at the end of the prompt lifecycle)
            await self._run_hooks(HookStage.AFTER_PROMPT_BUILD, HookContext(
                agent_name=getattr(self, "name", ""),
                agent_output=content,
                session_id=getattr(self, "session_id", ""),
                model=self.model,
                cwd=str(Path.cwd()),
                messages=list(updated_messages),
            ))
            return content

    async def _execute_tools_and_update_messages(
        self,
        response: MessageDict,
        messages: list[MessageDict],
        use_concurrent: bool = False
    ) -> list[MessageDict]:
        """
        Execute tool calls and update message history with results

        Args:
            response: LLM response with tool calls
            messages: Current message history
            use_concurrent: Whether to execute tools concurrently

        Returns:
            Updated message history
        """
        updated_messages = messages.copy()

        # Add assistant response to history
        updated_messages.append({
            "role": "assistant",
            "content": response.get("content", "")
        })

        # Execute tool calls
        raw_tool_calls = response.get("tool_calls", [])

        # Normalize ToolCall objects to dict format
        tool_calls: list[dict[str, Any]] = []
        for tc in raw_tool_calls:
            if hasattr(tc, "name") and hasattr(tc, "arguments"):
                # ToolCall dataclass
                tool_calls.append({
                    "function": {"name": tc.name, "arguments": tc.arguments},
                    "id": getattr(tc, "id", ""),
                })
            elif isinstance(tc, dict):
                tool_calls.append(tc)
            else:
                logger.warning("Unknown tool call type: %s", type(tc))

        tool_results: list[dict[str, Any]] = []

        if use_concurrent and len(tool_calls) > 1 and hasattr(self.tools, 'execute_tools_concurrent'):
            # Concurrent execution path
            tool_results = await self._execute_tools_concurrent(tool_calls)
        else:
            # Sequential execution path
            for tool_call in tool_calls:
                function_data = cast(dict[str, Any], tool_call["function"])
                tool_name = str(function_data["name"])
                tool_args_raw = function_data["arguments"]
                tool_call_id = str(tool_call.get("id", f"call_{len(tool_results)}"))

                try:
                    if isinstance(tool_args_raw, str):
                        tool_args = cast(dict[str, Any], json.loads(tool_args_raw))
                    else:
                        tool_args = cast(dict[str, Any], tool_args_raw)
                except json.JSONDecodeError:
                    tool_args = {}

                # Check permissions before executing
                decision = await self._should_execute_tool(tool_name, tool_args, tool_call_id)

                if decision.verdict == "skip":
                    # Tool execution skipped
                    tool_result_content = decision.feedback or f"Tool '{tool_name}' execution was skipped."
                    tool_results.append({
                        "tool": tool_name,
                        "success": False,
                        "result": None,
                        "error": decision.feedback,
                        "content": tool_result_content,
                        "skipped": True,
                    })
                    continue

                # Use updated args if provided by decision (e.g., from user input)
                if decision.updated_args:
                    tool_args = decision.updated_args

                # Invoke tool call callback if set
                if self.tool_call_callback:
                    self.tool_call_callback(tool_name, tool_args)

                # Run BEFORE_TOOL_CALL hooks
                before_ctx = HookContext(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    agent_name=getattr(self, "name", ""),
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                )
                before_result = await self._run_hooks(HookStage.BEFORE_TOOL_CALL, before_ctx)
                if before_result.block:
                    tool_result_content = f"Tool '{tool_name}' blocked by hook: {before_result.reason}"
                    tool_results.append({
                        "tool": tool_name,
                        "success": False,
                        "result": None,
                        "error": before_result.reason,
                        "content": tool_result_content,
                        "tool_call_id": tool_call_id,
                        "blocked": True,
                    })
                    continue
                # Use modified args if hook returned them
                if before_result.modify:
                    tool_args = {**tool_args, **before_result.modify}

                # Execute tool with retry for transient errors
                max_retries = 2  # Up to 2 retries (3 total attempts)
                result = None
                for attempt in range(max_retries + 1):
                    result = await self.tools.execute_tool(tool_name, tool_args)
                    success = getattr(result, "success", False)
                    err_val = getattr(result, "error", None)
                    # Only retry on transient infrastructure errors, not on tool logic errors
                    if success or not err_val or attempt == max_retries:
                        break
                    err_str = str(err_val).lower()
                    is_transient = any(
                        kw in err_str
                        for kw in ("rate limit", "timeout", "connection", "429", "503", "502", "500", "overloaded")
                    )
                    if not is_transient:
                        break
                    # Exponential backoff: 1s, 2s
                    import asyncio as _asyncio
                    await _asyncio.sleep(2 ** attempt)

                # Run AFTER_TOOL_CALL hooks
                success = getattr(result, "success", False)
                res_val = getattr(result, "result", None)
                err_val = getattr(result, "error", None)
                if not success and not err_val and res_val:
                    err_val = str(res_val)

                after_ctx = HookContext(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=res_val,
                    tool_error=err_val,
                    agent_name=getattr(self, "name", ""),
                    session_id=getattr(self, "session_id", ""),
                    model=self.model,
                    cwd=str(Path.cwd()),
                )
                after_result = await self._run_hooks(HookStage.AFTER_TOOL_CALL, after_ctx)

                if self.tool_result_callback:
                    self.tool_result_callback(tool_name, tool_args, result)

                # Record execution trace (best-effort, never fails the agent loop)
                try:
                    self.execution_trace.append(
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "success": bool(getattr(result, "success", False)),
                            "result": getattr(result, "result", None),
                            "error": getattr(result, "error", None),
                        }
                    )
                except Exception:
                    pass

                # Rebuild system prompt if a skill was activated
                if tool_name == "activate_skill" and hasattr(result, "success") and result.success:
                    skill_name = tool_args.get("skill_name", "") or tool_args.get("name", "")
                    # Run BEFORE_SKILL_ACTIVATE hooks
                    skill_ctx = HookContext(
                        skill_name=skill_name,
                        agent_name=getattr(self, "name", ""),
                        session_id=getattr(self, "session_id", ""),
                        model=self.model,
                        cwd=str(Path.cwd()),
                    )
                    await self._run_hooks(HookStage.BEFORE_SKILL_ACTIVATE, skill_ctx)
                    self.rebuild_system_prompt()
                    # Run AFTER_SKILL_ACTIVATE hooks
                    await self._run_hooks(HookStage.AFTER_SKILL_ACTIVATE, HookContext(
                        skill_name=skill_name,
                        agent_name=getattr(self, "name", ""),
                        session_id=getattr(self, "session_id", ""),
                        model=self.model,
                        cwd=str(Path.cwd()),
                    ))

                # Format tool result for LLM
                success = getattr(result, "success", False)
                res_val = getattr(result, "result", None)
                err_val = getattr(result, "error", None)

                # If error is None but there's a result with error info, use that
                if not success and not err_val and res_val:
                    err_val = str(res_val)

                if success:
                    tool_result_content = f"Tool {tool_name} executed successfully. Result: {res_val}"
                else:
                    tool_result_content = f"Tool {tool_name} failed. Error: {err_val}. Please adjust your approach and try again with different parameters."

                # Append injected content from AFTER_TOOL_CALL hooks (e.g. type errors)
                if after_result.inject:
                    tool_result_content += after_result.inject

                tool_results.append({
                    "tool": tool_name,
                    "success": success,
                    "result": res_val,
                    "error": err_val,
                    "content": tool_result_content,
                    "tool_call_id": tool_call_id,
                })

        # Add tool results to working message history as user message
        # (keeps the LLM loop running with proper alternation)
        tool_content = "\n".join([str(tr["content"]) for tr in tool_results])
        updated_messages.append({
            "role": "user",
            "content": tool_content
        })

        # Persist assistant message (with tool_calls) to memory for history
        self.add_role_message(
            role="assistant",
            content=response.get("content", ""),
            tool_calls=tool_calls,
        )

        # Persist tool result messages to memory (proper tool role)
        for tr in tool_results:
            self.add_role_message(
                role="tool",
                content=str(tr.get("content", "")),
                tool_call_id=str(tr.get("tool_call_id", "")),
            )

        # Also persist to conversation history if available
        if self.history is not None:
            from jarvis.core.history import (
                HistoryMessage,
            )
            self.history.append_message(
                HistoryMessage(
                    role="assistant",
                    content=response.get("content", ""),
                    tool_calls=tool_calls,
                )
            )
            for tr in tool_results:
                self.history.append_message(
                    HistoryMessage(
                        role="tool",
                        content=str(tr.get("content", "")),
                        tool_call_id=str(tr.get("tool_call_id", "")),
                    )
                )

        return updated_messages

    async def _execute_tools_concurrent(
        self,
        tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Execute multiple tool calls concurrently

        Args:
            tool_calls: List of tool call dictionaries

        Returns:
            List of tool result dictionaries
        """
        # First, check permissions for all tools
        approved_tool_calls = []
        skipped_results = []

        for tool_call in tool_calls:
            function_data = tool_call["function"]
            tool_name = str(function_data["name"])
            tool_args_raw = function_data["arguments"]
            tool_call_id = str(tool_call.get("id", ""))

            try:
                if isinstance(tool_args_raw, str):
                    tool_args = json.loads(tool_args_raw)
                else:
                    tool_args = tool_args_raw
            except json.JSONDecodeError:
                tool_args = {}

            # Check permissions before executing
            decision = await self._should_execute_tool(tool_name, tool_args, tool_call_id)

            if decision.verdict == "skip":
                skipped_results.append({
                    "tool": tool_name,
                    "success": False,
                    "result": None,
                    "error": decision.feedback,
                    "content": decision.feedback or f"Tool '{tool_name}' execution was skipped.",
                    "skipped": True,
                })
            else:
                # Use updated args if provided by decision (e.g., from user input)
                if decision.updated_args:
                    tool_args = decision.updated_args
                # Invoke tool call callback if set
                if self.tool_call_callback:
                    self.tool_call_callback(tool_name, tool_args)
                approved_tool_calls.append((tool_name, tool_args, tool_call))

        # Check if tools registry supports concurrent execution
        if hasattr(self.tools, 'execute_tools_concurrent') and approved_tool_calls:
            # Use async registry's concurrent execution
            tool_call_tuples = [(name, args) for name, args, _ in approved_tool_calls]

            from jarvis.core.tools.async_registry import AsyncToolRegistry
            async_registry = cast(AsyncToolRegistry, self.tools)
            tool_outputs = await async_registry.execute_tools_concurrent(tool_call_tuples)

            # Convert ToolOutput to result dictionaries
            results = []
            for i, output in enumerate(tool_outputs):
                tool_name, _, tool_call = approved_tool_calls[i]
                if self.tool_result_callback:
                    self.tool_result_callback(tool_name, tool_call["function"]["arguments"], output)

                # Record execution trace (best-effort)
                try:
                    # tool_call["function"]["arguments"] may be a JSON string; keep as-is to avoid parsing failures here
                    self.execution_trace.append(
                        {
                            "tool": tool_name,
                            "args": tool_call["function"]["arguments"],
                            "success": bool(getattr(output, "success", False)),
                            "result": getattr(output, "result", None),
                            "error": getattr(output, "error", None),
                        }
                    )
                except Exception:
                    pass

                # Rebuild system prompt if a skill was activated
                if tool_name == "activate_skill" and hasattr(output, "success") and output.success:
                    self.rebuild_system_prompt()

                # Format error message
                err_msg = output.error if output.error else "Unknown error"

                results.append({
                    "tool": tool_name,
                    "success": output.success,
                    "result": output.result,
                    "error": err_msg,
                    "tool_call_id": tool_call.get("id", ""),
                    "content": (
                        f"Tool {tool_name} executed successfully. Result: {output.result}"
                        if output.success
                        else f"Tool {tool_name} failed. Error: {err_msg}"
                    )
                })
            return skipped_results + results
        else:
            # Fallback to sequential execution
            results = skipped_results.copy()
            for tool_name, tool_args, tool_call in approved_tool_calls:
                result = await self.tools.execute_tool(tool_name, tool_args)
                if self.tool_result_callback:
                    self.tool_result_callback(tool_name, tool_call["function"]["arguments"], result)

                # Rebuild system prompt if a skill was activated
                if tool_name == "activate_skill" and hasattr(result, "success") and result.success:
                    self.rebuild_system_prompt()

                results.append({
                    "tool": tool_name,
                    "success": result.success,
                    "result": result.result,
                    "error": result.error,
                    "content": (
                        f"Tool {tool_name} executed successfully. Result: {result.result}"
                        if result.success
                        else f"Tool {tool_name} failed. Error: {result.error}"
                    )
                })
            return results

    async def _process_without_tools(
        self,
        messages: list[MessageDict],
        stream: bool = False
    ) -> str:
        """
        Process messages without tool calling

        Args:
            messages: Message history with proper roles
            stream: Whether to stream the response

        Returns:
            Generated response string
        """
        # Always try streaming when stream_callback is set (TUI mode)
        # This ensures real-time updates in the TUI
        if self.stream_callback:
            full_response = ""
            reasoning_content = ""
            try:
                stream_result = cast(
                    AsyncGenerator[Any, None],
                    await self.llm.generate(
                        messages=messages,
                        model=self.model,
                        stream=True,
                    ),
                )
                async for chunk in stream_result:
                    if isinstance(chunk, dict):
                        if chunk["type"] == "text":
                            chunk_text = cast(str, chunk["content"])
                            full_response += chunk_text
                            self.stream_callback(chunk_text)
                        elif chunk["type"] == "reasoning":
                            chunk_reasoning = cast(str, chunk["content"])
                            reasoning_content += chunk_reasoning
                            # Call reasoning callback if set and content exists
                            if chunk_reasoning and chunk_reasoning.strip():
                                if self.reasoning_callback:
                                    self.reasoning_callback(chunk_reasoning)
                    else:
                        # Backward compatibility for string chunks
                        chunk_text = str(chunk)
                        full_response += chunk_text
                        self.stream_callback(chunk_text)
                return full_response
            except Exception as e:
                logger.warning(f"Streaming failed, falling back to non-streaming: {e}")

        result = await self.llm.generate(
            messages=messages,
            model=self.model,
        )

        # Handle dict response
        if isinstance(result, dict):
            res_dict = cast(dict[str, Any], result)
            content = str(res_dict.get("content", ""))
            reasoning = str(res_dict.get("reasoning_content", "") or res_dict.get("reasoning", ""))

            # Call reasoning callback if set and content exists
            if reasoning and reasoning.strip() and self.reasoning_callback:
                self.reasoning_callback(reasoning)

            # Always emit content via stream_callback if set
            if self.stream_callback and content:
                self.stream_callback(content)

            return content

        # Handle string response
        if isinstance(result, str):
            if self.stream_callback and result:
                self.stream_callback(result)
            return result

        # Handle async generator response
        full_response = ""
        async for chunk in cast(AsyncGenerator[Any, None], result):
            if isinstance(chunk, dict):
                if chunk["type"] == "text":
                    chunk_text = cast(str, chunk["content"])
                    full_response += chunk_text
                elif chunk["type"] == "reasoning":
                    chunk_reasoning = cast(str, chunk["content"])
                    if chunk_reasoning and chunk_reasoning.strip() and self.reasoning_callback:
                        self.reasoning_callback(chunk_reasoning)
            else:
                full_response += str(chunk)

        # Always emit content via stream_callback if set
        if self.stream_callback and full_response:
            self.stream_callback(full_response)

        return full_response

    async def process_with_progress(
        self,
        input: str,
        context: dict[str, Any] | None = None
    ) -> str:
        """
        Process input with progress updates

        This method provides stage-based progress reporting with callbacks
        for user feedback during long-running operations.

        Args:
            input: User input string
            context: Optional context dictionary

        Returns:
            Agent response string
        """
        import time

        # Emit AgentStarted event
        ts = time.time()
        await self._emit(AgentStarted(timestamp=ts, agent_name=self.__class__.__name__, input=input))

        stages = ["Understanding", "Planning", "Execution", "Verification"]
        total_stages = len(stages)

        if self.status_callback:
            self.status_callback("Starting processing...")
        await self._emit(StatusUpdated(timestamp=time.time(), status="Starting processing...", message="Starting processing..."))

        # Stage 1: Understanding
        if self.progress_callback:
            self.progress_callback(stages[0], 0.0)
        if self.status_callback:
            self.status_callback(f"Stage 1/{total_stages}: {stages[0]}")
        await self._emit(ProgressUpdated(timestamp=time.time(), task=stages[0], progress=0.0))
        await asyncio.sleep(0)  # Yield control

        # Stage 2: Planning
        if self.progress_callback:
            self.progress_callback(stages[1], 0.25)
        if self.status_callback:
            self.status_callback(f"Stage 2/{total_stages}: {stages[1]}")
        await self._emit(ProgressUpdated(timestamp=time.time(), task=stages[1], progress=0.25))
        await asyncio.sleep(0)  # Yield control

        # Stage 3: Execution (the actual processing)
        if self.progress_callback:
            self.progress_callback(stages[2], 0.5)
        if self.status_callback:
            self.status_callback(f"Stage 3/{total_stages}: {stages[2]}")
        await self._emit(ProgressUpdated(timestamp=time.time(), task=stages[2], progress=0.5))

        # Process normally
        try:
            result = await self.process(input, context)
        except Exception as e:
            logger.exception("Processing failed")
            await self._emit(AgentError(timestamp=time.time(), agent_name=self.__class__.__name__, error=str(e)))
            raise

        # Stage 4: Verification
        if self.progress_callback:
            self.progress_callback(stages[3], 0.75)
        if self.status_callback:
            self.status_callback(f"Stage 4/{total_stages}: {stages[3]}")
        await self._emit(ProgressUpdated(timestamp=time.time(), task=stages[3], progress=0.75))
        await asyncio.sleep(0)  # Yield control

        # Complete
        if self.progress_callback:
            self.progress_callback("Complete", 1.0)
        if self.status_callback:
            self.status_callback("Processing complete")
        await self._emit(StatusUpdated(timestamp=time.time(), status="Complete", message="Processing complete"))
        await self._emit(AgentEnded(timestamp=time.time(), agent_name=self.__class__.__name__, output=result))

        return result

    def _get_background_task_manager(self):
        """Get or create the background task manager"""
        if self._background_task_manager is None:
            from jarvis.core.agents.background_task_manager import BackgroundTaskManager
            from jarvis.core.config.settings import Settings

            settings = self._config_getter() if self._config_getter else Settings()

            self._background_task_manager = BackgroundTaskManager(
                max_concurrent_tasks=settings.max_concurrent_agents,
                result_cache_ttl=3600,
                cleanup_interval=300
            )

            # Set the tool executor
            async def tool_executor(tool_name: str, tool_args: dict) -> Any:
                return await self.tools.execute_tool(tool_name, tool_args)

            self._background_task_manager.set_tool_executor(tool_executor)

        return self._background_task_manager

    async def delegate_to_background(
        self,
        task: str,
        tool_name: str,
        args: dict[str, Any],
        timeout: int = 300
    ) -> str:
        """
        Delegate a long-running task to background processing

        Args:
            task: Task description
            tool_name: Name of the tool to execute
            args: Tool arguments
            timeout: Timeout in seconds

        Returns:
            Task ID for tracking
        """
        try:
            # Get or create background task manager
            bg_manager = self._get_background_task_manager()

            # Submit task to background manager
            task_id = await bg_manager.submit_task(
                tool_name=tool_name,
                args=args,
                timeout=timeout
            )

            logger.info(f"Delegated task '{task}' to background with ID: {task_id}")
            return f"Task delegated to background. ID: {task_id}"

        except Exception as e:
            logger.error(f"Background task delegation failed: {e}")
            return f"Background task delegation failed: {str(e)}"
