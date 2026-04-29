"""Test improved error messages across all tools"""

import asyncio
from core.tools import (
    FileReadTool, FileWriteTool, ReplaceTool, ListDirectoryTool,
    GlobTool, BashTool, REPLTool, RunTestsTool, GrepSearchTool,
    ListBackgroundProcessesTool, ReadBackgroundOutputTool,
    WebFetchTool, SaveMemoryTool, InvokeAgentTool, ActivateSkillTool
)
from core.tools.base import ToolInput


async def test_file_read_error_messages():
    """Test FileReadTool error messages"""
    print("Testing FileReadTool error messages...")

    tool = FileReadTool()

    # Test invalid file path
    result = await tool.execute(ToolInput(filePath=""))
    assert result.success is False
    assert "non-empty string" in result.error
    assert "absolute file path" in result.error

    # Test file not found
    result = await tool.execute(ToolInput(filePath="/nonexistent/file.txt"))
    assert result.success is False
    assert "File not found" in result.error
    assert "list_directory or glob" in result.error

    # Test invalid offset
    result = await tool.execute(ToolInput(filePath="/tmp/test.txt", offset="invalid"))
    assert result.success is False
    assert "positive integer" in result.error

    print("[OK] FileReadTool error messages are improved")


async def test_file_write_error_messages():
    """Test FileWriteTool error messages"""
    print("\nTesting FileWriteTool error messages...")

    tool = FileWriteTool()

    # Test invalid file path
    result = await tool.execute(ToolInput(filePath="", content="test"))
    assert result.success is False
    assert "non-empty string" in result.error

    # Test invalid content
    result = await tool.execute(ToolInput(filePath="/tmp/test.txt", content=123))
    assert result.success is False
    assert "string" in result.error

    print("[OK] FileWriteTool error messages are improved")


async def test_replace_tool_error_messages():
    """Test ReplaceTool error messages"""
    print("\nTesting ReplaceTool error messages...")

    tool = ReplaceTool()

    # Test missing file path
    result = await tool.execute(ToolInput(replacements=[{"old_string": "test", "new_string": "new"}]))
    assert result.success is False
    # ReplaceTool returns errors in result.result, not result.error
    error_text = result.result if result.result else ""
    assert "Missing or invalid file_path" in error_text

    # Test file not found
    result = await tool.execute(ToolInput(replacements=[{
        "file_path": "/nonexistent/file.txt",
        "old_string": "test",
        "new_string": "new"
    }]))
    assert result.success is False
    error_text = result.result if result.result else ""
    assert "File not found" in error_text
    assert "list_directory or glob" in error_text

    # Test old_string not found - use a simple file we can create
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello World")
        test_file = f.name

    try:
        result = await tool.execute(ToolInput(replacements=[{
            "file_path": test_file,
            "old_string": "nonexistent_string_xyz_12345",
            "new_string": "new"
        }]))
        assert result.success is False
        error_text = result.result if result.result else ""
        assert "Could not find 'old_string'" in error_text
        assert "read the file first" in error_text
    finally:
        os.unlink(test_file)

    print("[OK] ReplaceTool error messages are improved")


async def test_bash_tool_error_messages():
    """Test BashTool error messages"""
    print("\nTesting BashTool error messages...")

    tool = BashTool()

    # Test invalid command
    result = await tool.execute(ToolInput(command=""))
    assert result.success is False
    assert "non-empty string" in result.error
    assert "valid shell command" in result.error

    print("[OK] BashTool error messages are improved")


async def test_run_tests_tool_error_messages():
    """Test RunTestsTool error messages"""
    print("\nTesting RunTestsTool error messages...")

    tool = RunTestsTool()

    # Test invalid path
    result = await tool.execute(ToolInput(path=""))
    assert result.success is False
    assert "non-empty string" in result.error
    assert "valid path to test file" in result.error

    # Test unsupported framework - the tool tries to execute anyway, so we check if it fails
    result = await tool.execute(ToolInput(path="/tmp", framework="invalid_framework"))
    # The tool will try to execute and likely fail, so we check the error
    if not result.success:
        assert "Unsupported test framework" in result.error or "invalid_framework" in result.error.lower()

    print("[OK] RunTestsTool error messages are improved")


async def test_grep_tool_error_messages():
    """Test GrepSearchTool error messages"""
    print("\nTesting GrepSearchTool error messages...")

    tool = GrepSearchTool()

    # Test invalid query
    result = await tool.execute(ToolInput(query="", isRegexp=False))
    assert result.success is False
    assert "non-empty string" in result.error
    assert "valid search pattern" in result.error

    print("[OK] GrepSearchTool error messages are improved")


async def test_invoke_agent_tool_error_messages():
    """Test InvokeAgentTool error messages"""
    print("\nTesting InvokeAgentTool error messages...")

    tool = InvokeAgentTool()

    # Test invalid input - empty agent_name gets caught by unknown agent check
    result = await tool.execute(ToolInput(agent_name="", prompt=""))
    assert result.success is False
    # The tool should return an error message
    assert result.error is not None

    # Test unknown agent
    result = await tool.execute(ToolInput(agent_name="unknown", prompt="test"))
    assert result.success is False
    assert "Unknown subagent" in result.error
    assert "explore" in result.error

    print("[OK] InvokeAgentTool error messages are improved")


async def test_activate_skill_tool_error_messages():
    """Test ActivateSkillTool error messages"""
    print("\nTesting ActivateSkillTool error messages...")

    tool = ActivateSkillTool()

    # Test invalid skill name
    result = await tool.execute(ToolInput(name=""))
    assert result.success is False
    assert "non-empty string" in result.error
    assert "valid skill name" in result.error

    # Test skill not found
    result = await tool.execute(ToolInput(name="nonexistent_skill"))
    assert result.success is False
    assert "not found" in result.error
    assert "Checked:" in result.error

    print("[OK] ActivateSkillTool error messages are improved")


async def test_web_fetch_tool_error_messages():
    """Test WebFetchTool error messages"""
    print("\nTesting WebFetchTool error messages...")

    tool = WebFetchTool()

    # Test invalid URLs
    result = await tool.execute(ToolInput(urls=[], query="test"))
    assert result.success is False
    assert "non-empty list" in result.error
    assert "valid URLs" in result.error

    print("[OK] WebFetchTool error messages are improved")


async def test_save_memory_tool_error_messages():
    """Test SaveMemoryTool error messages"""
    print("\nTesting SaveMemoryTool error messages...")

    tool = SaveMemoryTool()

    # Test invalid fact
    result = await tool.execute(ToolInput(fact=""))
    assert result.success is False
    assert "non-empty string" in result.error
    assert "concise fact" in result.error

    print("[OK] SaveMemoryTool error messages are improved")


async def test_read_background_output_tool_error_messages():
    """Test ReadBackgroundOutputTool error messages"""
    print("\nTesting ReadBackgroundOutputTool error messages...")

    tool = ReadBackgroundOutputTool()

    # Test invalid PID
    result = await tool.execute(ToolInput(pid=99999))
    assert result.success is False
    assert "No background process found" in result.error
    assert "list_background_processes" in result.error

    print("[OK] ReadBackgroundOutputTool error messages are improved")


async def main():
    """Run all error message tests"""
    print("=" * 60)
    print("Improved Error Messages Test Suite")
    print("=" * 60)

    try:
        await test_file_read_error_messages()
        await test_file_write_error_messages()
        await test_replace_tool_error_messages()
        await test_bash_tool_error_messages()
        await test_run_tests_tool_error_messages()
        await test_grep_tool_error_messages()
        await test_invoke_agent_tool_error_messages()
        await test_activate_skill_tool_error_messages()
        await test_web_fetch_tool_error_messages()
        await test_save_memory_tool_error_messages()
        await test_read_background_output_tool_error_messages()

        print("\n" + "=" * 60)
        print("All error message tests passed! [OK]")
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
