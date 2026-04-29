"""End-to-end test for JARVIS functionality"""

import asyncio
from core.agents import CodingAgent, ExploreAgent
from core.tools.registry import ToolRegistry
from core.tools import (
    FileReadTool, FileWriteTool, ReplaceTool, ListDirectoryTool,
    GlobTool, BashTool, REPLTool, RunTestsTool, GrepSearchTool,
    ListBackgroundProcessesTool, ReadBackgroundOutputTool,
    WebFetchTool, SaveMemoryTool, InvokeAgentTool, ActivateSkillTool,
    ReadPDFTool
)


async def test_system_prompt_in_messages():
    """Test that system prompt is correctly passed in messages"""
    print("Testing system prompt in messages...")

    # Create a mock tool registry
    tool_registry = ToolRegistry()

    # Create a mock LLM provider (we'll just test the structure)
    class MockLLMProvider:
        async def generate(self, messages, model=None, stream=False, **kwargs):
            # Check that system prompt is in messages
            assert messages[0]["role"] == "system", "First message should be system"
            assert "JARVIS" in messages[0]["content"], "System prompt should contain JARVIS"
            return "Mock response"

        async def generate_with_tools(self, messages, tools, model=None, stream=False, **kwargs):
            # Check that system prompt is in messages
            assert messages[0]["role"] == "system", "First message should be system"
            assert "JARVIS" in messages[0]["content"], "System prompt should contain JARVIS"
            return {"content": "Mock response", "tool_calls": []}

    # Create agent
    agent = CodingAgent(MockLLMProvider(), tool_registry, model="gpt-4o")

    # Test that process() doesn't duplicate system prompt
    messages = [{"role": "user", "content": "test"}]
    response = await agent.generate_response(messages, use_tools=False)

    print("[OK] System prompt correctly passed in messages")


async def test_no_stub_implementations():
    """Test that there are no stub/fake implementations"""
    print("\nTesting for stub implementations...")

    # Test that ActivateSkillTool has actual implementation by checking its code
    activate_tool_source = open("C:\\Users\\koula\\Desktop\\CODEBASE\\Projects\\OEvortex\\JARVIS\\core\\tools\\agent_tools.py").read()
    assert "skill_paths" in activate_tool_source, "ActivateSkillTool should have actual implementation"
    assert "os.path.exists" in activate_tool_source, "ActivateSkillTool should check for skill files"

    # Test that InvokeAgentTool has actual implementation
    assert "ExploreAgent" in activate_tool_source, "InvokeAgentTool should import ExploreAgent"
    assert "subagent.process" in activate_tool_source, "InvokeAgentTool should call subagent process"

    print("[OK] No stub implementations found")


async def test_skill_activation():
    """Test that skill activation actually works"""
    print("\nTesting skill activation...")

    tool_registry = ToolRegistry()
    activate_tool = ActivateSkillTool(tool_registry=tool_registry)

    # Try to activate a skill that doesn't exist
    from core.tools.base import ToolInput
    result = await activate_tool.execute(ToolInput(name="nonexistent-skill"))

    assert result.success is False, "Should fail for nonexistent skill"
    assert "not found" in result.error.lower(), "Error should mention skill not found"

    print("[OK] Skill activation properly handles missing skills")

    # Note: We can't test actual skill activation without a real skill file
    # but the implementation is now functional


async def test_explore_subagent_integration():
    """Test that explore subagent can be invoked"""
    print("\nTesting explore subagent integration...")

    from core.agents import ExploreAgent

    # Verify ExploreAgent exists and is properly implemented
    assert ExploreAgent is not None, "ExploreAgent should exist"

    # Check that it has proper system prompt
    from core.agents.explore_agent import EXPLORE_SYSTEM_PROMPT
    assert EXPLORE_SYSTEM_PROMPT is not None, "ExploreAgent should have system prompt"
    assert len(EXPLORE_SYSTEM_PROMPT) > 100, "System prompt should be substantial"

    print("[OK] Explore subagent is properly integrated")


async def test_tool_registry_provider_injection():
    """Test that tool registry properly injects provider references"""
    print("\nTesting tool registry provider injection...")

    tool_registry = ToolRegistry(llm_provider="mock_provider", model="gpt-4o")

    # Register a tool
    tool_registry.register(FileReadTool())

    # Check that tool has provider references
    file_read_tool = tool_registry.get("file_read")
    assert file_read_tool.tool_registry == tool_registry, "Tool should have tool_registry reference"
    assert file_read_tool.llm_provider == "mock_provider", "Tool should have llm_provider reference"
    assert file_read_tool.model == "gpt-4o", "Tool should have model reference"

    print("[OK] Tool registry properly injects provider references")


async def test_system_prompt_rebuild():
    """Test that system prompt rebuild works correctly"""
    print("\nTesting system prompt rebuild...")

    class MockLLMProvider:
        async def generate(self, messages, model=None, stream=False, **kwargs):
            return "Mock response"

        async def generate_with_tools(self, messages, tools, model=None, stream=False, **kwargs):
            return {"content": "Mock response", "tool_calls": []}

    tool_registry = ToolRegistry()
    agent = CodingAgent(MockLLMProvider(), tool_registry, model="gpt-4o")

    # Get initial system prompt
    initial_prompt = agent.system_prompt

    # Rebuild system prompt
    agent.rebuild_system_prompt()

    # Should still have system prompt
    assert agent.system_prompt is not None, "System prompt should exist after rebuild"
    assert len(agent.system_prompt) > 0, "System prompt should not be empty"

    print("[OK] System prompt rebuild works correctly")


async def test_skill_integration_in_system_prompt():
    """Test that activated skills are integrated into system prompt"""
    print("\nTesting skill integration in system prompt...")

    class MockLLMProvider:
        async def generate(self, messages, model=None, stream=False, **kwargs):
            return "Mock response"

        async def generate_with_tools(self, messages, tools, model=None, stream=False, **kwargs):
            return {"content": "Mock response", "tool_calls": []}

    tool_registry = ToolRegistry()
    agent = CodingAgent(MockLLMProvider(), tool_registry, model="gpt-4o")

    # Simulate skill activation by adding to tool registry
    tool_registry.active_skills = {
        "test-skill": "This is a test skill with some instructions."
    }

    # Rebuild system prompt
    agent.rebuild_system_prompt()

    # Check that skill is in system prompt
    assert "test-skill" in agent.system_prompt, "Activated skill should be in system prompt"
    assert "Active Skills" in agent.system_prompt, "Should have Active Skills section"

    print("[OK] Skills are integrated into system prompt")


async def main():
    """Run all end-to-end tests"""
    print("=" * 60)
    print("JARVIS End-to-End Test Suite")
    print("=" * 60)

    try:
        await test_system_prompt_in_messages()
        await test_no_stub_implementations()
        await test_skill_activation()
        await test_explore_subagent_integration()
        await test_tool_registry_provider_injection()
        await test_system_prompt_rebuild()
        await test_skill_integration_in_system_prompt()

        print("\n" + "=" * 60)
        print("All end-to-end tests passed! [OK]")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
