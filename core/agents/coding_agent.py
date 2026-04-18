"""Coding Agent - Claude Code style"""

from typing import Dict, List, Optional
from .base import BaseAgent
from .system_prompts import CODING_SYSTEM_PROMPT


class CodingAgent(BaseAgent):
    """Agent for coding tasks - Claude Code style"""

    SYSTEM_PROMPT = CODING_SYSTEM_PROMPT

    def __init__(self, llm_provider, tool_registry, model: Optional[str] = None):
        super().__init__(llm_provider, tool_registry, self.SYSTEM_PROMPT, model)

    async def process(self, input: str, context: Optional[Dict] = None) -> str:
        """
        Process a coding request

        Args:
            input: User input describing the coding task
            context: Optional context (e.g., current file, project path)

        Returns:
            Agent response with results or next steps
        """
        # Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._build_prompt(input, context)}
        ]

        # Add memory context if available
        memory_context = self.get_memory_context()
        if memory_context:
            messages.append({"role": "system", "content": memory_context})

        # Generate response with tool support and streaming
        stream = self.stream_callback is not None
        response = await self.generate_response(messages, use_tools=True, stream=stream)

        # Add to memory
        self.add_to_memory({
            "content": f"Task: {input}",
            "response": response[:500],  # Truncate for memory
            "type": "coding_task"
        })

        return response

    def _build_prompt(self, input: str, context: Optional[Dict]) -> str:
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

    async def plan(self, task: str) -> List[Dict]:
        """
        Plan the execution of a coding task

        Args:
            task: Task description

        Returns:
            List of action steps
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Plan the following coding task step by step:\n{task}\n\nReturn your plan as a numbered list of steps."}
        ]

        response = await self.generate_response(messages, use_tools=False)

        # Parse the plan into steps
        steps = self._parse_plan(response)
        return steps

    def _parse_plan(self, plan_text: str) -> List[Dict]:
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

    async def explore_codebase(self, path: str) -> Dict:
        """
        Explore a codebase structure

        Args:
            path: Path to the codebase

        Returns:
            Dictionary with codebase structure
        """
        # This would use file tools to explore the codebase
        # For now, return a placeholder
        return {
            "path": path,
            "structure": [],
            "message": "Codebase exploration not yet implemented"
        }

    async def make_edits(self, edits: List[Dict]) -> bool:
        """
        Apply multi-file edits

        Args:
            edits: List of edit dictionaries with file_path, old_content, new_content

        Returns:
            True if successful, False otherwise
        """
        # This would use file tools to make edits
        # For now, return a placeholder
        return False

    async def run_tests(self, test_path: str) -> Dict:
        """
        Run tests and analyze results

        Args:
            test_path: Path to tests or test command

        Returns:
            Dictionary with test results
        """
        # This would use code execution tools to run tests
        # For now, return a placeholder
        return {
            "test_path": test_path,
            "results": [],
            "message": "Test execution not yet implemented"
        }
