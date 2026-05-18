"""Test writer agent — specialized in writing and running tests.

Converted from examples/agents/test_writer.py to the extension API pattern.
"""

from jarvis.core.agents.agent_definition import AgentDefinition
from jarvis.core.agents.profiles import AgentType


def get_system_prompt() -> str:
    return """You are a test engineer. Your job is to write comprehensive tests for code.

Approach:
1. Read the source code to understand the interface
2. Identify test cases: happy path, edge cases, error conditions
3. Write tests following the project's existing test patterns
4. Run the tests and fix any failures
5. Verify coverage — ensure new code paths are tested

Rules:
- Match the project's existing test framework (pytest, unittest, jest, etc.)
- Write descriptive test names that explain what's being tested
- Use fixtures and helpers from the existing test suite
- Don't modify production code to make tests pass (unless it's a real bug)
- Aim for meaningful assertions, not just "no exception raised"
"""


async def jarvis(api):
    """Register the test writer agent."""
    api.agents(AgentDefinition(
        name="test-writer",
        agent_type=AgentType.SUBAGENT,
        description="Write tests for existing code, add test cases, improve test coverage, or debug failing tests. Use when the user asks to write tests, add coverage, or fix test failures.",
        tools=["read", "write", "edit", "grep", "find", "ls", "bash", "run_tests"],
        model="inherit",
        max_turns=50,
        system_prompt=get_system_prompt,
    ))
