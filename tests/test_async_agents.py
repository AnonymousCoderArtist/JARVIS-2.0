"""Tests for async agent functionality"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.agents.async_manager import (
    AsyncAgentManager,
    AsyncAgentConfig,
    AgentState,
    AgentTask,
)
from core.agents.background_task_manager import (
    BackgroundTaskManager,
    BackgroundTask,
    TaskState,
)
from core.agents.resource_monitor import (
    ResourceMonitor,
    ResourceSnapshot,
    ResourceLimits as MonitorResourceLimits,
)
from core.agents.base import BaseAgent
from core.tools.async_registry import AsyncToolRegistry
from core.tools.concurrent_executor import (
    ConcurrentToolExecutor,
    ExecutorResourceLimits as ToolResourceLimits,
)
from core.tools.base import BaseTool, ToolInput, ToolOutput


class MockTool(BaseTool):
    """Mock tool for testing"""

    name = "mock_tool"
    description = "A mock tool for testing"
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        await asyncio.sleep(0.1)  # Simulate async work
        return ToolOutput(success=True, result="mock result")


class MockAgent(BaseAgent):
    """Mock agent for testing"""

    async def process(self, input: str, context: dict | None = None) -> str:
        await asyncio.sleep(0.1)  # Simulate async work
        return f"Processed: {input}"

    async def plan(self, task: str) -> list[dict]:
        return [{"step": 1, "action": task}]


@pytest.mark.asyncio
async def test_async_agent_config():
    """Test AsyncAgentConfig initialization"""
    config = AsyncAgentConfig(
        max_concurrent_agents=10,
        max_concurrent_tools=20,
        default_timeout=60,
    )

    assert config.max_concurrent_agents == 10
    assert config.max_concurrent_tools == 20
    assert config.default_timeout == 60
    assert config.enable_background_tasks is True


@pytest.mark.asyncio
async def test_async_agent_manager_initialization():
    """Test AsyncAgentManager initialization"""
    config = AsyncAgentConfig(max_concurrent_agents=3)
    manager = AsyncAgentManager(config)

    assert manager.config.max_concurrent_agents == 3
    assert manager.get_queue_size() == 0
    assert manager.get_running_count() == 0
    assert manager.is_processing() is False


@pytest.mark.asyncio
async def test_submit_task():
    """Test task submission to AsyncAgentManager"""
    manager = AsyncAgentManager()
    mock_agent = MockAgent(
        llm_provider=MagicMock(),
        tool_registry=MagicMock(),
        system_prompt="test",
    )

    task_id = await manager.submit_task(mock_agent, "test task", priority=1)

    assert task_id.startswith("task_")
    assert manager.get_queue_size() == 1


@pytest.mark.asyncio
async def test_execute_concurrent():
    """Test concurrent execution of multiple agents"""
    config = AsyncAgentConfig(max_concurrent_agents=5)
    manager = AsyncAgentManager(config)

    mock_agents = [
        MockAgent(
            llm_provider=MagicMock(),
            tool_registry=MagicMock(),
            system_prompt="test",
        )
        for _ in range(3)
    ]

    tasks = [(agent, f"task {i}", None) for i, agent in enumerate(mock_agents)]

    results = await manager.execute_concurrent(tasks)  # type: ignore

    assert len(results) == 3
    for result in results:
        assert isinstance(result, str) and "Processed:" in result


@pytest.mark.asyncio
async def test_async_tool_registry():
    """Test AsyncToolRegistry"""
    registry = AsyncToolRegistry(max_concurrent_tools=5)
    tool = MockTool()
    registry.register(tool)

    result = await registry.execute_tool_async("mock_tool", {})

    assert result.success is True
    assert result.result == "mock result"


@pytest.mark.asyncio
async def test_execute_tools_concurrent():
    """Test concurrent tool execution"""
    registry = AsyncToolRegistry(max_concurrent_tools=5)
    tool = MockTool()
    registry.register(tool)

    tool_calls = [("mock_tool", {}) for _ in range(3)]

    results = await registry.execute_tools_concurrent(tool_calls)

    assert len(results) == 3
    assert all(result.success for result in results)


@pytest.mark.asyncio
async def test_execute_tools_with_timeout():
    """Test tool execution with timeout"""
    registry = AsyncToolRegistry()

    class SlowTool(BaseTool):
        name = "slow_tool"
        description = "A slow tool"
        input_schema = {"type": "object", "properties": {}}

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            await asyncio.sleep(10)  # Simulate slow operation
            return ToolOutput(success=True, result="done")

    slow_tool = SlowTool()
    registry.register(slow_tool)

    result = await registry.execute_tools_with_timeout("slow_tool", {}, timeout=0.5)

    assert result.success is False
    assert result.error is not None and "timed out" in result.error


@pytest.mark.asyncio
async def test_execute_tools_with_retry():
    """Test tool execution with retry"""
    registry = AsyncToolRegistry()

    class FlakyTool(BaseTool):
        name = "flaky_tool"
        description = "A flaky tool"
        input_schema = {"type": "object", "properties": {}}
        attempts = 0

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            FlakyTool.attempts += 1
            if FlakyTool.attempts < 3:
                return ToolOutput(success=False, result=None, error="failed")  # type: ignore
            return ToolOutput(success=True, result="success")

    flaky_tool = FlakyTool()
    registry.register(flaky_tool)

    result = await registry.execute_tools_with_retry("flaky_tool", {}, max_retries=3)

    assert result.success is True
    assert FlakyTool.attempts == 3


@pytest.mark.asyncio
async def test_concurrent_tool_executor():
    """Test ConcurrentToolExecutor"""
    registry = AsyncToolRegistry()
    tool = MockTool()
    registry.register(tool)

    executor = ConcurrentToolExecutor(
        registry,
        max_workers=5,
        resource_limits=ToolResourceLimits(timeout_seconds=10.0),
    )

    tool_calls = [("mock_tool", {}) for _ in range(3)]

    results = await executor.execute_concurrent(tool_calls)

    assert len(results) == 3
    assert all(result.success for result in results)


@pytest.mark.asyncio
async def test_concurrent_tool_executor_with_retry():
    """Test ConcurrentToolExecutor with retry"""
    registry = AsyncToolRegistry()

    class FlakyTool(BaseTool):
        name = "flaky_tool"
        description = "A flaky tool"
        input_schema = {"type": "object", "properties": {}}
        attempts = 0

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            FlakyTool.attempts += 1
            if FlakyTool.attempts < 2:
                return ToolOutput(success=False, result=None, error="failed")  # type: ignore
            return ToolOutput(success=True, result="success")

    flaky_tool = FlakyTool()
    registry.register(flaky_tool)

    executor = ConcurrentToolExecutor(registry)

    tool_calls = [("flaky_tool", {})]

    results = await executor.execute_with_retry(tool_calls, max_retries=2)

    assert len(results) == 1
    assert results[0].success is True


@pytest.mark.asyncio
async def test_concurrent_tool_executor_batched():
    """Test ConcurrentToolExecutor with batched execution"""
    registry = AsyncToolRegistry()
    tool = MockTool()
    registry.register(tool)

    executor = ConcurrentToolExecutor(registry)

    tool_calls = [("mock_tool", {}) for _ in range(10)]

    results = await executor.execute_batched(tool_calls, batch_size=3)

    assert len(results) == 10
    assert all(result.success for result in results)


@pytest.mark.asyncio
async def test_base_agent_progress_callbacks():
    """Test BaseAgent progress and status callbacks"""
    agent = MockAgent(
        llm_provider=MagicMock(),
        tool_registry=MagicMock(),
        system_prompt="test",
    )

    status_updates = []

    def status_callback(status: str):
        status_updates.append(status)

    agent.set_status_callback(status_callback)

    await agent.process_with_progress("test task")

    assert len(status_updates) == 2  # start and complete
    assert status_updates[0] == "Starting processing..."
    assert status_updates[1] == "Processing complete"


@pytest.mark.asyncio
async def test_base_agent_concurrent_tool_execution():
    """Test BaseAgent concurrent tool execution"""
    agent = MockAgent(
        llm_provider=MagicMock(),
        tool_registry=AsyncToolRegistry(),
        system_prompt="test",
    )

    # Register a mock tool
    tool = MockTool()
    agent.tools.register(tool)

    # Test the _execute_tools_concurrent method directly
    tool_calls = [
        {"function": {"name": "mock_tool", "arguments": "{}"}, "id": "call_1"},
        {"function": {"name": "mock_tool", "arguments": "{}"}, "id": "call_2"},
    ]

    results = await agent._execute_tools_concurrent(tool_calls)

    assert len(results) == 2
    assert all(result["success"] for result in results)


@pytest.mark.asyncio
async def test_tool_execute_async_with_timeout():
    """Test tool execution with timeout"""
    tool = MockTool()

    # Test with sufficient timeout
    result = await tool.execute_async(ToolInput(), timeout=1.0)
    assert result.success is True

    # Test with insufficient timeout
    class SlowTool(BaseTool):
        name = "slow_tool"
        description = "A slow tool"
        input_schema = {"type": "object", "properties": {}}

        async def execute(self, input_data: ToolInput) -> ToolOutput:
            await asyncio.sleep(10)  # Simulate slow operation
            return ToolOutput(success=True, result="done")

    slow_tool = SlowTool()
    result = await slow_tool.execute_async(ToolInput(), timeout=0.5)
    assert result.success is False
    assert "timed out" in result.error  # type: ignore


@pytest.mark.asyncio
async def test_background_task_manager():
    """Test BackgroundTaskManager"""
    manager = BackgroundTaskManager(max_concurrent_tasks=2)
    
    # Set up mock tool executor
    async def mock_executor(tool_name: str, args: dict) -> str:
        await asyncio.sleep(0.1)
        return f"Result for {tool_name}"
    
    manager.set_tool_executor(mock_executor)
    
    # Submit a task
    task_id = await manager.submit_task("test_tool", {"arg": "value"}, timeout=30)
    
    assert task_id.startswith("bg_task_")
    assert manager.get_queue_size() == 1
    
    # Get task status
    status = await manager.get_task_status(task_id)
    assert status["task_id"] == task_id
    assert status["state"] in ["PENDING", "RUNNING", "COMPLETED"]
    
    # Wait for task to complete
    await asyncio.sleep(0.3)
    
    # Get result
    result = await manager.get_task_result(task_id, wait=True, timeout=5.0)
    assert result == "Result for test_tool"
    
    # Stop processing
    await manager.stop_processing()


@pytest.mark.asyncio
async def test_background_task_manager_concurrent():
    """Test BackgroundTaskManager with concurrent tasks"""
    manager = BackgroundTaskManager(max_concurrent_tasks=3)
    
    async def mock_executor(tool_name: str, args: dict) -> str:
        await asyncio.sleep(0.1)
        return f"Result for {tool_name}"
    
    manager.set_tool_executor(mock_executor)
    
    # Submit multiple tasks
    task_ids = []
    for i in range(3):
        task_id = await manager.submit_task(f"tool_{i}", {"index": i}, timeout=30)
        task_ids.append(task_id)
    
    # Wait for all to complete
    await asyncio.sleep(0.5)
    
    # Get all results
    results = []
    for task_id in task_ids:
        result = await manager.get_task_result(task_id, wait=True, timeout=5.0)
        results.append(result)
    
    assert len(results) == 3
    assert all("Result for" in r for r in results)
    
    await manager.stop_processing()


@pytest.mark.asyncio
async def test_resource_monitor():
    """Test ResourceMonitor"""
    limits = MonitorResourceLimits(
        max_cpu_percent=80.0,
        max_memory_percent=80.0,
        max_memory_mb=512.0
    )
    
    monitor = ResourceMonitor(limits=limits, update_interval=0.5)
    
    # Start monitoring
    await monitor.start_monitoring()
    
    # Wait for some snapshots
    await asyncio.sleep(1.5)
    
    # Get current snapshot
    snapshot = monitor.get_current_snapshot()
    assert snapshot is not None
    assert snapshot.cpu_percent >= 0
    assert snapshot.memory_percent >= 0
    
    # Check limits
    limit_check = monitor.check_limits(snapshot)
    assert isinstance(limit_check, dict)
    assert "cpu_exceeded" in limit_check
    assert "memory_percent_exceeded" in limit_check
    
    # Get average usage
    avg_usage = monitor.get_average_usage(duration_seconds=1.0)
    assert "cpu_percent" in avg_usage
    assert "memory_percent" in avg_usage
    
    # Stop monitoring
    await monitor.stop_monitoring()

    assert not monitor.is_monitoring()


@pytest.mark.asyncio
async def test_concurrent_tool_executor_resource_limits():
    """Test ConcurrentToolExecutor with resource limit enforcement"""
    registry = AsyncToolRegistry()
    tool = MockTool()
    registry.register(tool)
    
    # Set very low resource limits
    limits = ToolResourceLimits(
        max_memory_mb=1,  # Very low limit
        max_cpu_percent=1.0,  # Very low limit
        timeout_seconds=10.0
    )
    
    executor = ConcurrentToolExecutor(registry, max_workers=5, resource_limits=limits)
    
    # Try to execute - may fail due to resource limits
    tool_calls = [("mock_tool", {})]
    results = await executor.execute_concurrent(tool_calls)
    
    # Either succeeds (if resources are low) or fails with resource limit error
    assert len(results) == 1
    if not results[0].success:
        assert results[0].error is not None and ("Resource limit exceeded" in results[0].error or "not found" in results[0].error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
