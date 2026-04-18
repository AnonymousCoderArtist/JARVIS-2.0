"""Knowledge Agent - Claude Coworker style"""

from typing import Dict, List, Optional
from .base import BaseAgent
from .system_prompts import KNOWLEDGE_SYSTEM_PROMPT


class KnowledgeAgent(BaseAgent):
    """Agent for knowledge work - Claude Coworker style"""

    SYSTEM_PROMPT = KNOWLEDGE_SYSTEM_PROMPT

    def __init__(self, llm_provider, tool_registry, model: Optional[str] = None):
        super().__init__(llm_provider, tool_registry, self.SYSTEM_PROMPT, model)

    async def process(self, input: str, context: Optional[Dict] = None) -> str:
        """
        Process a knowledge work request

        Args:
            input: User input describing the knowledge task
            context: Optional context (e.g., source files, criteria)

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
            "response": response[:500],
            "type": "knowledge_task"
        })

        return response

    def _build_prompt(self, input: str, context: Optional[Dict]) -> str:
        """Build the prompt for the knowledge task"""
        prompt = f"Task: {input}\n\n"

        if context:
            if "sources" in context:
                prompt += f"Sources: {context['sources']}\n"
            if "criteria" in context:
                prompt += f"Criteria: {context['criteria']}\n"
            if "source_content" in context:
                prompt += f"\nSource content:\n{context['source_content']}\n"

        return prompt

    async def plan(self, task: str) -> List[Dict]:
        """
        Plan the execution of a knowledge task

        Args:
            task: Task description

        Returns:
            List of action steps
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Plan the following knowledge work task step by step:\n{task}\n\nReturn your plan as a numbered list of steps."}
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

    async def organize_files(self, criteria: Dict) -> bool:
        """
        Organize files based on criteria

        Args:
            criteria: Dictionary with organization criteria

        Returns:
            True if successful, False otherwise
        """
        # This would use file tools to organize files
        # For now, return a placeholder
        return False

    async def prepare_document(self, sources: List[str], template: str) -> str:
        """
        Prepare a document from source files

        Args:
            sources: List of source file paths
            template: Document template or format

        Returns:
            Prepared document content
        """
        # This would use document processing tools
        # For now, return a placeholder
        return "Document preparation not yet implemented"

    async def synthesize_research(self, sources: List[str]) -> str:
        """
        Synthesize research from multiple sources

        Args:
            sources: List of source file paths or content

        Returns:
            Synthesized research summary
        """
        # This would use document processing and analysis tools
        # For now, return a placeholder
        return "Research synthesis not yet implemented"

    async def extract_data(self, source: str, schema: Dict) -> List[Dict]:
        """
        Extract structured data from unstructured files

        Args:
            source: Source file path or content
            schema: Data schema for extraction

        Returns:
            List of extracted data records
        """
        # This would use document processing tools
        # For now, return a placeholder
        return []
