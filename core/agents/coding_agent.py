"""Coding Agent - Claude Code style"""


from .base import BaseAgent
from .system_prompts import JARVIS_V2_SYSTEM_PROMPT, EXPLORE_SYSTEM_PROMPT, PLAN_SYSTEM_PROMPT


# Mapping from system_prompt_id to system prompts
SYSTEM_PROMPT_MAP = {
    "jarvis": JARVIS_V2_SYSTEM_PROMPT,
    "explore": EXPLORE_SYSTEM_PROMPT,
    "plan": PLAN_SYSTEM_PROMPT,
}


class CodingAgent(BaseAgent):
    """JARVIS - Single agent for all tasks"""

    SYSTEM_PROMPT = JARVIS_V2_SYSTEM_PROMPT

    def __init__(self, llm_provider, tool_registry, model: str | None = None, config_getter=None, bypass_tool_permissions: bool = False, use_concurrent_tools: bool = True, system_prompt: str | None = None):
        # Use provided system_prompt or default to JARVIS_V2_SYSTEM_PROMPT
        effective_prompt = system_prompt if system_prompt else self.SYSTEM_PROMPT
        super().__init__(llm_provider, tool_registry, effective_prompt, model, config_getter, bypass_tool_permissions, use_concurrent_tools)
        # Rebuild system prompt with tool descriptions
        self.rebuild_system_prompt()

    def set_system_prompt(self, system_prompt: str) -> None:
        """Set a new system prompt for the agent."""
        self.system_prompt = system_prompt
        self.rebuild_system_prompt()

    @classmethod
    def get_system_prompt_for_profile(cls, system_prompt_id: str | None) -> str:
        """Get the appropriate system prompt for a profile's system_prompt_id."""
        if system_prompt_id and system_prompt_id in SYSTEM_PROMPT_MAP:
            return SYSTEM_PROMPT_MAP[system_prompt_id]
        return cls.SYSTEM_PROMPT  # Default to JARVIS_V2_SYSTEM_PROMPT

    async def process(self, input: str, context: dict | None = None) -> str:
        """
        Process a coding request

        Args:
            input: User input describing the coding task
            context: Optional context (e.g., current file, project path)

        Returns:
            Agent response with results or next steps
        """
        # Build messages with proper roles using base class method
        user_content = self._build_prompt(input, context)
        messages = self._build_messages(user_content, include_memory=True)

        # Always use streaming when stream_callback is set (TUI mode)
        # This ensures real-time updates in the TUI
        stream = self.stream_callback is not None
        response = await self._process_with_tools(messages, stream=stream)

        # Add to memory
        self.add_to_memory({
            "content": f"Task: {input}",
            "response": response,
            "type": "coding_task"
        })

        return response

    def _build_prompt(self, input: str, context: dict | None) -> str:
        """Build the prompt for the coding task"""
        prompt = f"Task: {input}\n\n"

        if context:
            if "current_file" in context:
                prompt += f"Current file: {context['current_file']}\n"
            if "project_path" in context:
                prompt += f"Project path: {context['project_path']}\n"
            if "file_content" in context:
                prompt += f"\nFile content:\n{context['file_content']}\n"

        return prompt

    async def plan(self, task: str) -> list[dict]:
        """
        Plan the execution of a coding task

        Args:
            task: Task description

        Returns:
            List of action steps
        """
        # Build messages with proper roles
        user_content = f"Plan the following coding task step by step:\n{task}\n\nReturn your plan as a numbered list of steps."
        messages = self._build_messages(user_content, include_memory=False)

        # Process without tools
        response = await self._process_without_tools(messages, stream=False)

        # Parse the plan into steps
        steps = self._parse_plan(response)
        return steps

    def _parse_plan(self, plan_text: str) -> list[dict]:
        """Parse plan text into structured steps"""
        steps = []
        lines = plan_text.split('\n')

        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                steps.append({
                    "description": line,
                    "completed": False
                })

        return steps
