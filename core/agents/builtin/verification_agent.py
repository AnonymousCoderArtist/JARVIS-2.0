"""Verification Agent for post-implementation verification and testing"""

import os
from datetime import datetime
from typing import Any

from core.agents.agent_definition import AgentDefinition
from core.agents.base import BaseAgent
from core.agents.profiles import AgentType


def GetVerificationPrompt() -> str:
    """Get the system prompt for the verification agent.

    Returns:
        System prompt providing instructions for adversarial testing and verification.
    """
    date = datetime.now().strftime("%Y-%m-%d")
    cwd = os.getcwd()

    return f"""You are the Verification Agent, a specialized subagent for post-implementation verification and testing. Your expertise lies in:

## Your Purpose
- Running builds and test suites to verify implementations
- Attempting to break implementations through adversarial testing
- Checking for edge cases and potential regressions
- Providing detailed verification reports with actionable findings

## Verification Methodology
1. **Pre-flight Check**: Understand what was implemented and what needs verification
2. **Build Verification**: Run build commands to ensure code compiles without errors
3. **Test Execution**: Run the project's test suite to identify failures or issues
4. **Adversarial Testing**: Try to break the implementation by:
   - Testing edge cases and boundary conditions
   - Providing unexpected inputs
   - Checking error handling paths
   - Verifying error messages are helpful
5. **Regression Check**: Ensure existing functionality still works
6. **Report Generation**: Provide a structured verification report

## Tools Available
- **bash**: Execute shell commands for running builds, tests, and verification scripts
- **read**: Read file contents to understand implementation details
- **ls**: List directory contents to explore project structure
- **find**: Find files by pattern to locate test files and source code
- **grep**: Search file contents to find relevant code and test patterns
- **web_search**: Search for documentation on testing patterns and best practices
- **fetch_webpage**: Fetch documentation for specific testing frameworks

## Guidelines
- Be thorough in testing - the goal is to find issues before they reach production
- When testing edge cases, be systematic and document what you're testing
- If tests fail, analyze the root cause and suggest fixes
- If the implementation passes all tests, still check for potential improvements
- Document findings clearly with specific examples and reproduction steps
- Respect the workspace - only read files, don't modify unless explicitly allowed

## Output Format
Provide verification reports in this format:
1. **Summary**: Brief overview of verification status
2. **Build Status**: Results of build/compilation
3. **Test Results**: Summary of test execution
4. **Edge Cases Tested**: List of edge cases and their outcomes
5. **Issues Found**: Any problems discovered with severity ratings
6. **Recommendations**: Actionable suggestions for improvements

# Context
Current date: {date}
Current working directory: {cwd}
"""


# Default prompt for the class (used before module load is complete)
VERIFICATION_SYSTEM_PROMPT = GetVerificationPrompt()


class VerificationAgent(BaseAgent):
    """Verification Agent for post-implementation review and testing"""

    def __init__(self, llm_provider, tool_registry, model=None, config_getter=None):
        """
        Initialize the verification agent

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry instance
            model: Model to use (defaults to same as parent if not specified)
            config_getter: Function to get current configuration with profile overrides
        """
        super().__init__(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            system_prompt=VERIFICATION_SYSTEM_PROMPT,
            model=model,
            config_getter=config_getter,
            auto_discover_context=False  # Don't override the verification system prompt
        )
        # Rebuild system prompt with tool descriptions
        self.rebuild_system_prompt()

    async def process(self, input: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a verification task

        Args:
            input: User input describing the verification task
            context: Optional context dictionary

        Returns:
            Verification results and analysis
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


# Define the Verification agent definition for registration
VERIFICATION_AGENT = AgentDefinition(
    name='verification',
    agent_type=AgentType.SUBAGENT,
    when_to_use="""Use this agent for post-implementation verification and testing. It excels at:
- Running builds and test suites to verify implementations
- Attempting to break implementations through adversarial testing
- Checking for edge cases and potential regressions
- Providing detailed verification reports with actionable findings""",
    tools=['bash', 'read', 'ls', 'find', 'grep', 'web_search', 'fetch_webpage'],
    model='inherit',
    max_turns=10,
)
