"""Plan subagent for task decomposition and planning"""

from typing import Any

from core.agents.base import BaseAgent
from core.agents.system_prompts import PLAN_SYSTEM_PROMPT


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
            system_prompt=PLAN_SYSTEM_PROMPT,
            model=model,
            config_getter=config_getter
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

    async def plan(self, task: str) -> list[dict[str, Any]]:
        """
        Plan an execution task

        Args:
            task: Task description

        Returns:
            List of planning steps
        """
        # Build messages for planning
        user_content = f"""Plan the following task step by step:

{task}

Provide a detailed plan with:
1. Phase breakdown (e.g., Analysis, Implementation, Testing, Verification)
2. Specific steps for each phase
3. Dependencies between steps
4. Potential risks or edge cases
5. How to verify each step succeeds

Return your plan in a structured format."""

        messages = self._build_messages(user_content, include_memory=False)

        # Process without tools for initial planning
        response = await self._process_without_tools(messages, stream=False)

        # Parse the plan into structured steps
        steps = self._parse_plan(response)
        return steps

    def _parse_plan(self, plan_text: str) -> list[dict[str, Any]]:
        """Parse plan text into structured steps"""
        steps = []
        lines = plan_text.split('\n')

        current_phase = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect phase headers (e.g., "Phase 1:", "Analysis:", "## Analysis")
            if line.lower().startswith('phase') or line.endswith(':') and len(line) < 30:
                current_phase = line.rstrip(':').strip()
                continue

            # Detect step items (numbered or bulleted)
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                # Clean up the step text
                step_text = line.lstrip('0123456789.-* ').strip()
                if step_text:
                    steps.append({
                        "phase": current_phase,
                        "description": step_text,
                        "completed": False
                    })

        return steps if steps else [{"phase": "General", "description": plan_text, "completed": False}]