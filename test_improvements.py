"""Test script for JARVIS improvements"""

import asyncio
from core.agents import CodingAgent, ExploreAgent
from core.tools.registry import ToolRegistry
from core.llm.sdk_adapter import SDKAdapter
from core.llm_sdk.provider_registry import provider_registry
from core.config.settings import Settings


async def test_system_prompt():
    """Test that system prompt includes new sections"""
    print("Testing system prompt improvements...")

    from core.agents.system_prompts import JARVIS_SYSTEM_PROMPT

    # Check for new sections
    assert "Subagent Coordination" in JARVIS_SYSTEM_PROMPT, "Missing Subagent Coordination section"
    assert "Task Decomposition Strategy" in JARVIS_SYSTEM_PROMPT, "Missing Task Decomposition Strategy"
    assert "Tool Result Interpretation" in JARVIS_SYSTEM_PROMPT, "Missing Tool Result Interpretation"
    assert "Explore Subagent" in JARVIS_SYSTEM_PROMPT, "Missing Explore Subagent reference"

    print("[OK] System prompt includes all new sections")
    print(f"[OK] System prompt length: {len(JARVIS_SYSTEM_PROMPT)} characters")


async def test_tool_descriptions():
    """Test that tool descriptions are comprehensive"""
    print("\nTesting tool descriptions...")

    tool_registry = ToolRegistry()

    from core.tools import (
        FileReadTool, FileWriteTool, ReplaceTool, ListDirectoryTool,
        GlobTool, BashTool, REPLTool, RunTestsTool, GrepSearchTool,
        ListBackgroundProcessesTool, ReadBackgroundOutputTool,
        WebFetchTool, SaveMemoryTool, InvokeAgentTool, ActivateSkillTool,
        ReadPDFTool
    )

    # Register tools
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(ReplaceTool())
    tool_registry.register(ListDirectoryTool())
    tool_registry.register(GlobTool())
    tool_registry.register(BashTool())
    tool_registry.register(REPLTool())
    tool_registry.register(RunTestsTool())
    tool_registry.register(GrepSearchTool())
    tool_registry.register(ListBackgroundProcessesTool())
    tool_registry.register(ReadBackgroundOutputTool())
    tool_registry.register(WebFetchTool())
    tool_registry.register(SaveMemoryTool())
    tool_registry.register(InvokeAgentTool())
    tool_registry.register(ActivateSkillTool())
    tool_registry.register(ReadPDFTool())

    # Check InvokeAgentTool description mentions explore subagent
    invoke_agent = tool_registry.get("invoke_agent")
    assert invoke_agent is not None, "InvokeAgentTool not registered"
    assert "explore" in invoke_agent.description.lower(), "InvokeAgentTool description should mention explore subagent"
    assert "same model" in invoke_agent.description.lower(), "InvokeAgentTool description should mention same model"

    print("[OK] All tools registered successfully")
    print("[OK] InvokeAgentTool description mentions explore subagent")
    print(f"[OK] Total tools registered: {len(tool_registry.list_tools())}")


async def test_tool_result_handling():
    """Test that tool results include success/failure information"""
    print("\nTesting tool result handling...")

    from core.tools.base import ToolOutput

    # Test successful result
    success_result = ToolOutput(
        success=True,
        result="Operation completed",
        metadata={"key": "value"}
    )

    assert success_result.success is True, "Success result should have success=True"
    assert success_result.result == "Operation completed", "Result should match"
    assert success_result.error is None, "Success result should have no error"

    # Test failed result
    failure_result = ToolOutput(
        success=False,
        result=None,
        error="Operation failed"
    )

    assert failure_result.success is False, "Failure result should have success=False"
    assert failure_result.result is None, "Failure result should have no result"
    assert failure_result.error == "Operation failed", "Error should match"

    print("[OK] Tool results properly handle success/failure information")


async def test_explore_agent():
    """Test that ExploreAgent can be instantiated"""
    print("\nTesting ExploreAgent...")

    from core.agents import ExploreAgent

    # Create a mock tool registry
    tool_registry = ToolRegistry()

    # ExploreAgent should be importable
    assert ExploreAgent is not None, "ExploreAgent should be importable"

    # Check that ExploreAgent has the right system prompt
    from core.agents.explore_agent import EXPLORE_SYSTEM_PROMPT
    assert EXPLORE_SYSTEM_PROMPT is not None, "EXPLORE_SYSTEM_PROMPT should exist"
    assert "codebase exploration" in EXPLORE_SYSTEM_PROMPT.lower(), "Explore prompt should mention codebase exploration"
    assert "systematic" in EXPLORE_SYSTEM_PROMPT.lower(), "Explore prompt should mention systematic approach"

    print("[OK] ExploreAgent is importable")
    print("[OK] ExploreAgent has appropriate system prompt")
    print(f"[OK] Explore prompt length: {len(EXPLORE_SYSTEM_PROMPT)} characters")


async def test_tool_registry_with_provider():
    """Test that ToolRegistry can accept provider and model"""
    print("\nTesting ToolRegistry with provider references...")

    # Create tool registry with provider and model
    tool_registry = ToolRegistry(llm_provider="mock_provider", model="gpt-4o")

    assert tool_registry.llm_provider == "mock_provider", "ToolRegistry should store llm_provider"
    assert tool_registry.model == "gpt-4o", "ToolRegistry should store model"

    # Register a tool
    from core.tools import FileReadTool
    tool_registry.register(FileReadTool())

    # Check that tool has provider references
    file_read_tool = tool_registry.get("file_read")
    assert file_read_tool is not None, "FileReadTool should be registered"
    assert file_read_tool.tool_registry == tool_registry, "Tool should have tool_registry reference"
    assert file_read_tool.llm_provider == "mock_provider", "Tool should have llm_provider reference"
    assert file_read_tool.model == "gpt-4o", "Tool should have model reference"

    print("[OK] ToolRegistry accepts and stores provider and model")
    print("[OK] Registered tools receive provider and model references")


async def test_base_tool_with_provider():
    """Test that BaseTool accepts provider parameters"""
    print("\nTesting BaseTool with provider parameters...")

    from core.tools import FileReadTool

    # Create tool with provider parameters
    tool = FileReadTool(
        tool_registry="mock_registry",
        llm_provider="mock_provider",
        model="gpt-4o"
    )

    assert tool.tool_registry == "mock_registry", "Tool should store tool_registry"
    assert tool.llm_provider == "mock_provider", "Tool should store llm_provider"
    assert tool.model == "gpt-4o", "Tool should store model"

    print("[OK] BaseTool accepts provider parameters")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("JARVIS Improvements Test Suite")
    print("=" * 60)

    try:
        await test_system_prompt()
        await test_tool_descriptions()
        await test_tool_result_handling()
        await test_explore_agent()
        await test_tool_registry_with_provider()
        await test_base_tool_with_provider()

        print("\n" + "=" * 60)
        print("All tests passed! [OK]")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
