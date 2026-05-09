import pytest
import os
from core.tools.registry import ToolRegistry
from pathlib import Path

@pytest.mark.asyncio
async def test_discover_and_register_plugins():
    registry = ToolRegistry()
    
    # Call the method
    count = registry.discover_and_register_plugins()
    
    # Verify that at least the calc tool we just created was registered
    # (assuming it's in .jarvis/tools/ in the project root)
    assert "calc" in registry._tools
    
    # Execute the tool to make sure it works
    output = await registry.execute_tool("calc", {"expression": "10 * 5"})
    assert output.success
    assert output.result == "50"
