"""Base agent architecture"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from typing import Any, cast

from core.llm.base import BaseLLMProvider
from core.llm_sdk.base.sdk import ToolCall
from core.tools.registry import ToolRegistry
from core.agents.system_prompts import generate_tool_descriptions, get_system_context


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        system_prompt: str,
        model: str | None = None,
    ):
        self.llm = llm_provider
        self.tools = tool_registry
        self.base_system_prompt = system_prompt
        self.model = model or "gpt-4"  # Use provided model or default
        self.memory: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}
        # Callbacks for streaming and tool calls
        self.stream_callback: Callable | None = None
        self.tool_call_callback: Callable | None = None
        self.tool_result_callback: Callable | None = None
        
        # Dynamically build full system prompt with tool descriptions
        self._build_system_prompt()
    
    def _build_system_prompt(self):
        """Build the full system prompt with dynamically injected tool descriptions."""
        # Get system context
        system_context = get_system_context()
        
        # Get tool descriptions from the tool registry
        tools_dict = self.tools.get_tools()
        tool_descriptions = generate_tool_descriptions(tools_dict)
        
        # Combine base prompt with system context and tool descriptions
        full_prompt = self.base_system_prompt
        if system_context:
            full_prompt = f"{full_prompt}\n\n{system_context}"
        if tool_descriptions:
            full_prompt = f"{full_prompt}\n\n{tool_descriptions}"
        
        self.system_prompt = full_prompt

    def rebuild_system_prompt(self):
        """Rebuild the system prompt with current tool descriptions.
        
        Call this after modifying the tool registry to update the agent's
        system prompt with the latest tool descriptions.
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

    def add_to_memory(self, entry: dict[str, Any]):
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
            context_parts.append(f"- {entry.get('content', '')}")

        return "Relevant context:\n" + "\n".join(context_parts)

    def update_context(self, key: str, value: Any):
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

    def clear_memory(self):
        """Clear agent memory"""
        self.memory = []

    async def generate_response(
        self,
        messages: list[dict[str, Any]],
        use_tools: bool = False,
        stream: bool = False,
        **kwargs: Any
    ) -> str:
        """
        Generate a response using the LLM

        Args:
            messages: List of message dictionaries
            use_tools: Whether to use tool calling
            stream: Whether to stream the response
            **kwargs: Additional parameters for generation

        Returns:
            Generated response string
        """
        # Ensure system prompt is the first message
        if messages and messages[0].get("role") != "system":
            messages = [{"role": "system", "content": self.system_prompt}] + messages
        elif messages:
            messages[0]["content"] = self.system_prompt
        
        if use_tools:
            tool_definitions = self.tools.get_function_definitions()

            # Try to use streaming with tools
            if stream and self.stream_callback:
                full_response = ""
                tool_calls = []
                try:
                    # Use the streaming endpoint with tools - await first, then iterate
                    stream_result = cast(
                        AsyncGenerator[Any, None],
                        await self.llm.generate_with_tools(
                        messages=messages,
                        tools=tool_definitions,
                        model=self.model,
                        stream=True,
                        **kwargs
                        ),
                    )
                    async for chunk in stream_result:
                        if isinstance(chunk, dict):
                            if chunk["type"] == "text":
                                full_response += chunk["content"]
                                self.stream_callback(chunk["content"])
                            elif chunk["type"] == "tool_calls":
                                # Handle tool_calls from OpenAI SDK streaming
                                for tc in chunk.get("tool_calls", []):
                                    tool_calls.append(ToolCall(
                                        id=tc.get("id", ""),
                                        name=tc.get("name", ""),
                                        arguments=tc.get("arguments", "")
                                    ))
                            elif chunk["type"] == "tool_call":
                                # Handle tool_call from Anthropic SDK streaming
                                tool_calls.append(chunk["tool_call"])
                        else:
                            # Fallback for string chunks
                            full_response += chunk
                            self.stream_callback(chunk)

                    # If tool calls were encountered, execute them
                    if tool_calls:
                        # Create a response object with the tool calls
                        response = {
                            "content": full_response,
                            "tool_calls": [{"function": {"name": tc.name, "arguments": tc.arguments}} for tc in tool_calls]
                        }
                        final_response = await self._handle_tool_calls(response, messages, full_response)
                        return final_response

                    return full_response
                except Exception:
                    # If streaming fails, fall back to non-streaming
                    pass

            # Non-streaming fallback
            raw_response = await self.llm.generate_with_tools(
                messages=messages,
                tools=tool_definitions,
                model=self.model,
                **kwargs
            )
            response = cast(dict[str, Any], raw_response)

            content = response.get("content", "")
            if stream and self.stream_callback and content:
                self.stream_callback(content)

            if response.get("tool_calls"):
                return await self._handle_tool_calls(response, messages, content)

            return content
        else:
            if stream and self.stream_callback:
                # Stream the response character by character
                full_response = ""
                stream_result = cast(
                    AsyncGenerator[Any, None],
                    await self.llm.generate(
                    messages=messages,
                    model=self.model,
                    stream=True,
                    **kwargs
                    ),
                )
                async for chunk in stream_result:
                    chunk_text = chunk if isinstance(chunk, str) else str(chunk)
                    full_response += chunk_text
                    self.stream_callback(chunk_text)
                return full_response
            else:
                result = await self.llm.generate(
                    messages=messages,
                    model=self.model,
                    **kwargs
                )
                if isinstance(result, str):
                    return result

                full_response = ""
                async for chunk in cast(AsyncGenerator[Any, None], result):
                    full_response += chunk if isinstance(chunk, str) else str(chunk)
                return full_response

    async def _handle_tool_calls(
        self,
        response: dict[str, Any],
        messages: list[dict[str, Any]],
        existing_content: str = ""
    ) -> str:
        """
        Handle tool calls from LLM response with recursive loop (OpenClaude style agentic pattern)

        This implements the agentic loop pattern:
        1. Call LLM with conversation history
        2. If tool calls, execute them and add results to history
        3. Repeat until LLM returns no tool calls
        4. Return final response

        Args:
            response: LLM response with tool calls
            messages: Original message history
            existing_content: Content already streamed before tool calls

        Returns:
            Final response after recursive tool execution
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
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]

            try:
                if isinstance(tool_args_str, str):
                    tool_args = json.loads(tool_args_str)
                else:
                    tool_args = tool_args_str
            except json.JSONDecodeError:
                tool_args = {}

            # Invoke tool call callback if set
            if self.tool_call_callback:
                self.tool_call_callback(tool_name, tool_args)

            result = await self.tools.execute_tool(tool_name, tool_args)
            if self.tool_result_callback:
                self.tool_result_callback(tool_name, tool_args, result)
            
            # Format tool result for LLM (OpenClaude style)
            if result.success:
                tool_result_content = f"Tool {tool_name} executed successfully. Result: {result.result}"
            else:
                tool_result_content = f"Tool {tool_name} failed. Error: {result.error}"
            
            tool_results.append({
                "tool": tool_name,
                "success": result.success,
                "result": result.result,
                "error": result.error,
                "content": tool_result_content
            })

        # Add tool results to conversation history (OpenClaude style format)
        updated_messages.append({
            "role": "user",
            "content": "\n".join([tr["content"] for tr in tool_results])
        })

        # Recursive loop: call LLM again with updated history
        tool_definitions = self.tools.get_function_definitions()
        next_response = await self.llm.generate_with_tools(
            messages=updated_messages,
            tools=tool_definitions,
            model=self.model
        )

        if isinstance(next_response, dict):
            resp = cast(dict[str, Any], next_response)
            # Check for further tool calls in the dict response
            if resp.get("tool_calls"):
                return await self._handle_tool_calls(resp, updated_messages, existing_content)

            # No more tool calls, stream and return final content
            final_content = resp.get("content", "")
            if self.stream_callback and final_content:
                self.stream_callback(final_content)
            return existing_content + final_content
        else:
            # Streaming generator: iterate and handle streamed chunks
            async for chunk in next_response:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    text = chunk.get("content", "")
                    if self.stream_callback and text:
                        self.stream_callback(text)
                    existing_content += text

                # If tool calls appear in stream, recurse using the dict form
                if isinstance(chunk, dict) and chunk.get("type") == "tool_calls":
                    return await self._handle_tool_calls(chunk, updated_messages, existing_content)

            return existing_content
