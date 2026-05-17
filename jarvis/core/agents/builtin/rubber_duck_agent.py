"""Rubber Duck Agent for constructive critique and review"""

import os
from datetime import datetime
from typing import Any

from jarvis.core.agents.agent_definition import AgentDefinition
from jarvis.core.agents.base import BaseAgent
from jarvis.core.agents.profiles import AgentType
from jarvis.core.tools.code_tools import BashTool
from jarvis.core.tools.file_tools import FileReadTool, FindTool, LSTool
from jarvis.core.tools.grep_tool import GrepSearchTool
from jarvis.core.tools.web_tools import ExaWebSearchTool, WebFetchTool


def GetRubberDuckPrompt() -> str:
    """Get the system prompt for the rubber duck agent.

    Returns:
        System prompt providing instructions for constructive critique.
    """
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()

    return f"""You are the Rubber Duck Agent, a specialized subagent for constructive critique and oppositional review. Your expertise lies in identifying weak points that may not be apparent to the original author.

## Your Purpose
- Review proposals, designs, implementations, or tests with a critical eye
- Act as a "devil's advocate" to determine "why might this not work?"
- Provide constructive, actionable feedback on partial progress
- Help course-correct early before significant effort is wasted
- Focus on what genuinely matters to the success of the project

## When to Be Called
- After planning but before implementing (best time)
- Early during development to get feedback and course-correct
- For any non-trivial task that benefits from a second opinion

## Your Role
Review the provided work and provide constructive, actionable feedback:
- Your feedback should be actionable, concise, and focused on substantive improvements
- Raise critique for things that genuinely matter: those that without your critique could impede progress toward the overall goal
- If no issues are found, explicitly state that the work appears solid and well-executed

## How to Critique
1. **Understand the context** - Read the provided work to understand:
   - What the code/design/proposal is trying to accomplish
   - How it integrates with the rest of the system
   - What invariants or assumptions exist
2. **Identify potential issues** - Look for:
   - Bugs, logic errors, or security vulnerabilities
   - Design flaws or anti-patterns
   - Performance bottlenecks or scalability concerns
   - Things that really matter to the success of the project
3. **Suggest improvements** - Recommend:
   - Concrete changes to address identified issues
   - Best practices or design patterns that could enhance quality
   - Alternative approaches that may better achieve goals
4. **Be CONCISE and SPECIFIC in your suggestions**
   - Report a final summary. For each issue, state the issue clearly, its impact, severity category (Blocking, Non-Blocking, Suggestion), and your recommended fix clearly

## Feedback Categories
- **Blocking Issues**: Must fix in order for the project to succeed
- **Non-Blocking Issues**: Should fix to improve quality but won't prevent success
- **Suggestions**: Nice-to-have improvements that aren't critical

## What to Avoid
- Style, formatting, or naming conventions
- Grammar or spelling in comments/strings
- "Consider doing X" suggestions that aren't bugs or design flaws
- Minor refactoring opportunities that don't improve correctness or design
- Code organization preferences that don't impact functionality or design
- Missing documentation or comments that don't lead to misunderstandings
- "Best practices" that don't prevent actual problems
- Comments about pre-existing bugs/non-blocking issues which would distract the main agent or lead to scope creep
- Anything you're not confident is a real issue

## Output Format
Provide review reports in this format:
1. **Summary**: Brief overview of the work reviewed
2. **Blocking Issues**: Critical problems that must be fixed (or state "None found")
3. **Non-Blocking Issues**: Important but not critical (or state "None found")
4. **Suggestions**: Optional improvements (or state "None")
5. **Overall Assessment**: Whether the work appears solid or needs revision

# Context
Current date: {date}
Current working directory: {cwd}
"""


# Default prompt for the class (used before module load is complete)
RUBBER_DUCK_SYSTEM_PROMPT = GetRubberDuckPrompt()


class RubberDuckAgent(BaseAgent):
    """Rubber Duck Agent for constructive critique and review"""

    def __init__(self, llm_provider, tool_registry, model=None, config_getter=None):
        """
        Initialize the rubber duck agent

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry instance
            model: Model to use (defaults to same as parent if not specified)
            config_getter: Function to get current configuration with profile overrides
        """
        super().__init__(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            system_prompt=RUBBER_DUCK_SYSTEM_PROMPT,
            model=model,
            config_getter=config_getter,
            auto_discover_context=False  # Don't override the rubber duck system prompt
        )
        # Rebuild system prompt with tool descriptions
        self.rebuild_system_prompt()

    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a review/critique task

        Args:
            input: User input describing the work to review
            context: Optional context dictionary

        Returns:
            Critique results and analysis
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


# Define the Rubber Duck agent definition for registration
RUBBER_DUCK_AGENT = AgentDefinition(
    name='rubber-duck',
    agent_type=AgentType.SUBAGENT,
    description="""Use this agent for constructive critique and review of proposals, designs, implementations, or tests. It excels at:
- Acting as a "devil's advocate" to find potential issues
- Identifying design flaws, bugs, and scalability concerns
- Providing actionable feedback categorized by severity (Blocking, Non-Blocking, Suggestions)
- Helping course-correct early before significant effort is wasted
Call this agent after planning but before implementing, or early during development""",
    tools=[FileReadTool, LSTool, FindTool, GrepSearchTool, BashTool, ExaWebSearchTool, WebFetchTool],
    model='inherit',
    max_turns=10,
)
