"""Explore subagent for codebase exploration and analysis"""

from typing import Any

from core.agents.base import BaseAgent
from core.agents.system_prompts import get_agent_prompt


class ExploreAgent(BaseAgent):
    """Explore subagent for codebase exploration and analysis"""

    def __init__(self, llm_provider, tool_registry, model=None, config_getter=None):
        """
        Initialize the explore agent

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry instance
            model: Model to use (defaults to same as parent if not specified)
            config_getter: Function to get current configuration with profile overrides
        """
        # Use the same model as provided, or default
        super().__init__(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            system_prompt=get_agent_prompt("explore"),
            model=model,
            config_getter=config_getter
        )
        # Rebuild system prompt with tool descriptions
        self.rebuild_system_prompt()

    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """
        Process an exploration task

        Args:
            input: User input describing the exploration task
            context: Optional context dictionary

        Returns:
            Exploration results and analysis
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

    async def plan(self, task: str) -> list[dict[str, Any]]:
        """
        Plan an exploration task

        Args:
            task: Exploration task description

        Returns:
            List of exploration steps
        """
        # For exploration, we don't need detailed planning
        # The agent will explore systematically using tools
        return [
            {"step": "analyze_structure", "action": "Examine project structure"},
            {"step": "identify_components", "action": "Identify key components"},
            {"step": "analyze_dependencies", "action": "Analyze dependencies"},
            {"step": "synthesize", "action": "Synthesize findings"}
        ]