"""Base agent architecture"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, TypeAlias, cast

from core.agents.system_prompts import get_system_context
from core.llm.base import BaseLLMProvider, MessageDict, ToolDefDict
from core.llm_sdk.base.sdk import ToolCall
from core.config.settings import Settings
from core.tools.permissions import ApprovedRule, PermissionContext, ToolPermission
from core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Type aliases for messages and tool definitions
# MessageDict and ToolDefDict are imported from core.llm.base

# Type aliases for callbacks
StreamCallback: TypeAlias = Callable[[str], None]
ToolCallCallback: TypeAlias = Callable[[str, dict[str, Any]], None]
ToolResultCallback: TypeAlias = Callable[[str, dict[str, Any], Any], None]
ReasoningCallback: TypeAlias = Callable[[str], None]
ApprovalCallback: TypeAlias = Callable[[str, dict[str, Any], str, list[Any]], Any]
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
    ):
        self.llm: BaseLLMProvider = llm_provider
        self.tools: ToolRegistry = tool_registry
        self.base_system_prompt: str = system_prompt
        self.system_prompt: str = ""
        self.model: str = model or "gpt-4"  # Use provided model or default
        self.memory: list[MessageDict] = []
        self.context: dict[str, Any] = {}
        # Callbacks for streaming and tool calls
        self.stream_callback: StreamCallback | None = None
        self.tool_call_callback: ToolCallCallback | None = None
        self.tool_result_callback: ToolResultCallback | None = None
        self.reasoning_callback: ReasoningCallback | None = None

        # Permission system
        self.approval_callback: ApprovalCallback | None = None
        self._session_rules: list[ApprovedRule] = []
        self._config_getter: ConfigGetter = config_getter or (lambda: Settings())
        self.bypass_tool_permissions: bool = bypass_tool_permissions

        # Dynamically build full system prompt with tool descriptions
        self._build_system_prompt()
    
    def _build_system_prompt(self) -> None:
        """Build the full system prompt with system context and active skills."""
        # Get system context
        system_context = get_system_context()

        # Combine base prompt with system context
        full_prompt = self.base_system_prompt
        if system_context:
            full_prompt = f"{full_prompt}\n\n{system_context}"

        # Add active skills if any
        if hasattr(self.tools, 'active_skills') and self.tools.active_skills:
            skills_section = "\n\n## Active Skills\n\n"
            active_skills = cast(dict[str, str], self.tools.active_skills)
            for skill_name, skill_content in active_skills.items():
                skills_section += f"### {skill_name}\n{skill_content}\n\n"
            full_prompt += skills_section

        # Add available skills information dynamically
        try:
            from core.skills import SkillManager
            skill_manager = SkillManager()
            available_skills = skill_manager.get_skill_descriptions_for_prompt()
            if available_skills:
                full_prompt += "\n\n" + available_skills
        except Exception:
            # If skill manager fails, continue without skill descriptions
            pass

        self.system_prompt = full_prompt

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
            entry: Dictionary with memory entry data
        """
        self.memory.append(entry)

    def get_memory_context(self, limit: int = 5) -> str:
        """
        Get formatted memory context

        Args:
            limit: Maximum number of memory entries to include

        Returns:
            Formatted memory context string
        """
        recent_memory = self.memory[-limit:] if self.memory else []
        if not recent_memory:
            return ""

        context_parts = []
        for entry in recent_memory:
            content = entry.get('content', '')
            if content:
                context_parts.append(f"- {content}")

        return "Relevant context:\n" + "\n".join(context_parts)

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
        from core.tools.utils import wildcard_match

        return any(
            rule.tool_name == tool_name
            and rule.scope == required_permission.scope
            and wildcard_match(
                required_permission.invocation_pattern, rule.session_pattern
            )
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

            if response == ApprovalResponse.YES:
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
            # Set tool-level permission
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
            else:
                # Store in session (would need session-level config)
                pass

    def _build_messages(self, user_content: str, include_memory: bool = True) -> list[MessageDict]:
        """
        Build message list with system, user, and memory context

        Args:
            user_content: User input content
            include_memory: Whether to include memory context

        Returns:
            List of message dictionaries with proper roles
        """
        messages: list[MessageDict] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # Add memory context if available
        if include_memory:
            memory_context = self.get_memory_context()
            if memory_context:
                messages.append({"role": "system", "content": memory_context})

        # Add user message
        messages.append({"role": "user", "content": user_content})

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

        Args:
            messages: Message history with proper roles
            stream: Whether to stream the response

        Returns:
            Final response after tool execution
        """
        tool_definitions = self.tools.get_function_definitions()
        updated_messages = messages.copy()

        while True:
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
                            elif chunk["type"] == "tool_calls":
                                for tc in cast(list[dict[str, Any]], chunk.get("tool_calls", [])):
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

                    # If tool calls were encountered, execute them
                    if tool_calls:
                        response_dict: dict[str, Any] = {
                            "content": full_response,
                            "tool_calls": [{"function": {"name": tc.name, "arguments": tc.arguments}, "id": tc.id} for tc in tool_calls]
                        }
                        updated_messages = await self._execute_tools_and_update_messages(response_dict, updated_messages)
                        continue  # Loop again with updated messages

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
                return await self._process_without_tools(updated_messages, stream=stream)
            
            # Handle response
            response: MessageDict = cast(MessageDict, raw_response)

            content = str(response.get("content", ""))
            reasoning = str(response.get("reasoning_content", "") or response.get("reasoning", ""))
            
            # Handle reasoning content in non-streaming mode
            if reasoning and reasoning.strip() and self.reasoning_callback:
                self.reasoning_callback(reasoning)
            
            # Always emit content via stream_callback if set, even in non-streaming mode
            if self.stream_callback and content:
                self.stream_callback(content)

            if response.get("tool_calls"):
                updated_messages = await self._execute_tools_and_update_messages(response, updated_messages)
                continue  # Loop again with updated messages

            return content

    async def _execute_tools_and_update_messages(
        self,
        response: MessageDict,
        messages: list[MessageDict]
    ) -> list[MessageDict]:
        """
        Execute tool calls and update message history with results

        Args:
            response: LLM response with tool calls
            messages: Current message history

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
        tool_calls = cast(list[dict[str, Any]], response.get("tool_calls", []))
        tool_results: list[dict[str, Any]] = []

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

            # Invoke tool call callback if set
            if self.tool_call_callback:
                self.tool_call_callback(tool_name, tool_args)

            result = await self.tools.execute_tool(tool_name, tool_args)
            if self.tool_result_callback:
                self.tool_result_callback(tool_name, tool_args, result)

            # Rebuild system prompt if a skill was activated
            if tool_name == "activate_skill" and hasattr(result, "success") and result.success:
                self.rebuild_system_prompt()

            # Format tool result for LLM
            success = getattr(result, "success", False)
            res_val = getattr(result, "result", None)
            err_val = getattr(result, "error", "Unknown error")

            if success:
                tool_result_content = f"Tool {tool_name} executed successfully. Result: {res_val}"
            else:
                tool_result_content = f"Tool {tool_name} failed. Error: {err_val}. Please adjust your approach and try again with different parameters."

            tool_results.append({
                "tool": tool_name,
                "success": success,
                "result": res_val,
                "error": err_val,
                "content": tool_result_content
            })

        # Add tool results to conversation history as user message
        updated_messages.append({
            "role": "user",
            "content": "\n".join([str(tr["content"]) for tr in tool_results])
        })

        return updated_messages

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
