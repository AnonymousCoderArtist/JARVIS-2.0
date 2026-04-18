"""Base agent architecture"""

import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from core.llm.base import BaseLLMProvider
from core.tools.registry import ToolRegistry


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        system_prompt: str,
        model: Optional[str] = None,
    ):
        self.llm = llm_provider
        self.tools = tool_registry
        self.system_prompt = system_prompt
        self.model = model or "gpt-4"  # Use provided model or default
        self.memory: List[Dict] = []
        self.context: Dict[str, any] = {}
        # Callbacks for streaming and tool calls
        self.stream_callback: Optional[callable] = None
        self.tool_call_callback: Optional[callable] = None

    @abstractmethod
    async def process(self, input: str, context: Optional[Dict] = None) -> str:
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
    async def plan(self, task: str) -> List[Dict]:
        """
        Plan the execution of a task

        Args:
            task: Task description

        Returns:
            List of action steps
        """
        pass

    def add_to_memory(self, entry: Dict):
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

    def update_context(self, key: str, value: any):
        """
        Update the agent's context

        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value

    def get_context(self, key: str, default: any = None) -> any:
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
        messages: List[Dict],
        use_tools: bool = False,
        stream: bool = False,
        **kwargs
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
        if use_tools:
            tool_definitions = self.tools.get_function_definitions()

            # When using tools, we can't stream during the tool call itself
            # But we can stream the content before and after
            if stream and self.stream_callback:
                # Get the response with tools
                response = await self.llm.generate_with_tools(
                    messages=messages,
                    tools=tool_definitions,
                    model=self.model,
                    **kwargs
                )

                # Stream the initial content
                initial_content = response.get("content", "")
                if initial_content:
                    self.stream_callback(initial_content)

                # Handle tool calls if present
                if response.get("tool_calls"):
                    final_response = await self._handle_tool_calls(response, messages, initial_content)
                    # Stream the final response
                    if final_response and final_response != initial_content:
                        self.stream_callback(final_response[len(initial_content):])
                    return final_response

                return initial_content
            else:
                response = await self.llm.generate_with_tools(
                    messages=messages,
                    tools=tool_definitions,
                    model=self.model,
                    **kwargs
                )

                # Handle tool calls if present
                if response.get("tool_calls"):
                    return await self._handle_tool_calls(response, messages)

                return response.get("content", "")
        else:
            if stream and self.stream_callback:
                # Stream the response
                full_response = ""
                async for chunk in self.llm.generate(
                    messages=messages,
                    model=self.model,
                    stream=True,
                    **kwargs
                ):
                    full_response += chunk
                    self.stream_callback(chunk)
                return full_response
            else:
                return await self.llm.generate(
                    messages=messages,
                    model=self.model,
                    **kwargs
                )

    async def _handle_tool_calls(
        self,
        response: Dict,
        messages: List[Dict],
        existing_content: str = ""
    ) -> str:
        """
        Handle tool calls from LLM response with recursive loop

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
        tool_calls = response.get("tool_calls", [])
        tool_results = []

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
            tool_results.append({
                "tool": tool_name,
                "success": result.success,
                "result": result.result,
                "error": result.error
            })

        # Add tool results to conversation history
        updated_messages.append({
            "role": "user",
            "content": f"Tool results: {json.dumps(tool_results, indent=2)}"
        })
        
        # Recursive loop: call LLM again with updated history
        tool_definitions = self.tools.get_function_definitions()
        next_response = await self.llm.generate_with_tools(
            messages=updated_messages,
            tools=tool_definitions,
            model=self.model
        )

        # Check if there are more tool calls
        if next_response.get("tool_calls"):
            # Continue the recursive loop
            return await self._handle_tool_calls(next_response, updated_messages, existing_content)
        else:
            # No more tool calls, stream and return final content
            final_content = next_response.get("content", "")
            if self.stream_callback and final_content:
                self.stream_callback(final_content)
            return existing_content + final_content
