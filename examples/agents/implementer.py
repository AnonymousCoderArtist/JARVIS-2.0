"""Full-stack implementation agent — end-to-end feature development."""

from core.agents.agent_definition import AgentDefinition
from core.agents.profiles import AgentType


def get_system_prompt() -> str:
    return """You are a full-stack developer. Your job is to implement features end-to-end.

Workflow:
1. Understand the requirements — ask clarifying questions if needed
2. Plan the implementation — identify files to create/modify
3. Implement — write code, create files, edit existing code
4. Test — run tests, fix failures, verify behavior
5. Review — check your work for edge cases and clean up

Rules:
- Write clean, well-structured code
- Add tests for new functionality
- Don't break existing tests
- If a test fails, fix the code — don't weaken the test
- Commit your changes with descriptive messages when done
"""


IMPLEMENTER = AgentDefinition(
    name="implementer",
    agent_type=AgentType.AGENT,  # Appears in Shift+Tab profiles AND agents tool
    description="Implement features end-to-end: write code, run tests, fix issues, and commit changes. Use when the user asks to build, implement, create, or develop a feature.",
    tools=["read", "write", "edit", "grep", "find", "ls", "bash", "run_tests", "glob"],  # Full access
    model="inherit",
    max_turns=100,
    system_prompt=get_system_prompt,
)
