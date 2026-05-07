"""Plan subagent for task decomposition and planning"""

from typing import Any

from core.agents.base import BaseAgent
from core.agents.system_prompts import get_agent_prompt


class PlanAgent(BaseAgent):
    """Plan subagent for task decomposition and planning"""

    def __init__(self, llm_provider, tool_registry, model=None, config_getter=None):
        """
        Initialize the plan agent

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry instance
            model: Model to use (defaults to same as parent if not specified)
            config_getter: Function to get current configuration with profile overrides
        """
        super().__init__(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            system_prompt=get_agent_prompt("plan"),
            model=model,
            config_getter=config_getter,
            auto_discover_context=False  # Don't override the plan system prompt
        )
        # Rebuild system prompt with tool descriptions
        self.rebuild_system_prompt()

    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a planning task

        Args:
            input: User input describing the planning task
            context: Optional context dictionary

        Returns:
            Plan with structured steps and details
        """
        # Build user content with context if provided
        user_content = input
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            user_content = f"{input}\n\nContext:\n{context_str}"

        # Build messages with proper roles using base class method
        messages = self._build_messages(user_content, include_memory=False)

        # Process with tool support
        stream = self.stream_callback is not None
        response = await self._process_with_tools(messages, stream=stream)

        return response