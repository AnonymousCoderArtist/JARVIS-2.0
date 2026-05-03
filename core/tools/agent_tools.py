"""Agent and Skill management tools"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


# Global background agent tracker
_background_agents: dict[str, 'BackgroundAgentTask'] = {}
_background_lock = asyncio.Lock()


@dataclass
class BackgroundAgentTask:
    """Represents a background agent task"""
    task_id: str
    agent_name: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    task: asyncio.Task | None = None


async def get_background_agent(task_id: str) -> BackgroundAgentTask | None:
    """Get a background agent task by ID"""
    async with _background_lock:
        return _background_agents.get(task_id)


async def list_background_agents() -> list[BackgroundAgentTask]:
    """List all background agent tasks"""
    async with _background_lock:
        return list(_background_agents.values())


async def _run_agent_in_background(
    task_id: str,
    agent_name: str,
    prompt: str,
    llm_provider,
    tool_registry,
    model,
    config_getter,
):
    """Run an agent in the background and update status when done"""
    from core.agents import EXPLORE, ExploreAgent, PLAN, PlanAgent
    from core.config.settings import Settings

    try:
        # Update status to running
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "running"

        # Create the appropriate subagent
        if agent_name == "explore":
            def explore_config_getter() -> Settings:
                if callable(config_getter):
                    base_settings = config_getter()
                else:
                    base_settings = Settings()
                merged_config = EXPLORE.apply_to_config(base_settings.model_dump())
                return Settings(initial_config=merged_config)

            explore_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=("read", "ls", "find", "grep"),
                llm_provider=llm_provider,
                model=model,
                config_getter=explore_config_getter,
            )

            subagent = ExploreAgent(
                llm_provider=llm_provider,
                tool_registry=explore_registry,
                model=model,
                config_getter=explore_config_getter,
            )
            subagent.rebuild_system_prompt()

            # Execute the task
            result = await subagent.process(prompt)

            # Update with result
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].completed_at = datetime.now()

        elif agent_name == "plan":
            def plan_config_getter() -> Settings:
                if callable(config_getter):
                    base_settings = config_getter()
                else:
                    base_settings = Settings()
                merged_config = PLAN.apply_to_config(base_settings.model_dump())
                return Settings(initial_config=merged_config)

            plan_registry = _FilteredToolRegistry(
                tool_registry,
                allowed_tools=("read", "ls", "find", "grep", "web_search", "fetch_webpage", "save_memory", "read_memory"),
                llm_provider=llm_provider,
                model=model,
                config_getter=plan_config_getter,
            )

            subagent = PlanAgent(
                llm_provider=llm_provider,
                tool_registry=plan_registry,
                model=model,
                config_getter=plan_config_getter,
            )
            subagent.rebuild_system_prompt()

            # Execute the task
            result = await subagent.process(prompt)

            # Update with result
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "completed"
                    _background_agents[task_id].result = result
                    _background_agents[task_id].completed_at = datetime.now()

        else:
            async with _background_lock:
                if task_id in _background_agents:
                    _background_agents[task_id].status = "failed"
                    _background_agents[task_id].error = f"Unknown agent: {agent_name}"
                    _background_agents[task_id].completed_at = datetime.now()

    except Exception as e:
        async with _background_lock:
            if task_id in _background_agents:
                _background_agents[task_id].status = "failed"
                _background_agents[task_id].error = str(e)
                _background_agents[task_id].completed_at = datetime.now()


class _FilteredToolRegistry:
    """Read-only filtered view over a tool registry."""

    def __init__(
        self,
        source_registry,
        allowed_tools: Iterable[str],
        llm_provider=None,
        model=None,
        config_getter=None,
    ):
        self._source_registry = source_registry
        self._allowed_tools = set(allowed_tools)
        self.llm_provider = llm_provider
        self.model = model
        self.config_getter = config_getter
        self.active_skills = getattr(source_registry, "active_skills", {})

    def get(self, name: str):
        if name not in self._allowed_tools:
            return None
        return self._source_registry.get(name)

    def get_tools(self) -> dict[str, BaseTool]:
        return {
            name: tool
            for name, tool in self._source_registry.get_tools().items()
            if name in self._allowed_tools
        }

    def list_tools(self) -> list[dict[str, object]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.get_tools().values()
        ]

    def get_function_definitions(self) -> list[dict[str, object]]:
        return [tool.get_function_definition() for tool in self.get_tools().values()]

    async def execute_tool(self, name: str, input_data: dict) -> ToolOutput:
        if name not in self._allowed_tools:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Tool '{name}' is not available to the explore subagent.",
            )
        return await self._source_registry.execute_tool(name, input_data)


def get_skill_description() -> str:
    """Get dynamic skill descriptions from SkillManager"""
    try:
        from core.skills import SkillManager
        skill_manager = SkillManager()
        return skill_manager.get_skill_descriptions_for_prompt()
    except Exception:
        # Fallback to basic description if skill manager fails
        return "Skills not available. Please ensure the SkillManager is properly implemented and accessible."


class AgentsTool(BaseTool):
    """Tool for invoking specialized agents"""

    name = "agents"
    description = """Invoke specialized subagents (explore, plan) for specific tasks.

WHEN TO USE:
- explore: Need to understand codebase structure, find files, analyze patterns
- plan: Need to decompose complex tasks, create implementation plans

Parameters:
- agent_name (REQUIRED): 'explore' for codebase analysis, 'plan' for task planning
- prompt (REQUIRED): Task description or query to send to the agent
- runInBackground (REQUIRED): Set true for async when delegating multiple tasks, false for immediate results

Examples:
- Synchronous: {"agentName": "explore", "prompt": "Find all API endpoints", "runInBackground": false}
- Background: {"agentName": "plan", "prompt": "Plan auth system", "runInBackground": true}

Returns: Agent response (sync) or background task ID (async)."""
    input_schema = {
        "type": "object",
        "properties": {
            "agentName": {
                "type": "string",
                "description": "Name of the specialized subagent to invoke (e.g., 'explore')",
                "minLength": 1
            },
            "prompt": {
                "type": "string",
                "description": "The complete query or task to send to the subagent",
                "minLength": 1
            },
            "runInBackground": {
                "type": "boolean",
                "description": "REQUIRED: Set to true ONLY when delegating multiple tasks and can do other work. Set to false for single tasks needing immediate result."
            }
        },
        "required": ["agentName", "prompt", "runInBackground"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support camelCase parameter names
        agent_name = self._get_param(input_data, "agentName")
        prompt = self._get_param(input_data, "prompt")
        runInBackground = self._get_param(input_data, "runInBackground") or False

        if not isinstance(agent_name, str) or not isinstance(prompt, str):
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid agent invocation input: agentName and prompt must be non-empty strings. Please provide a valid agent name and a descriptive task prompt."
            )

        # Import here to avoid circular dependencies
        try:
            # Check if the tool has access to the registry and provider
            if not hasattr(self, 'tool_registry') or not hasattr(self, 'llm_provider'):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Agent tool not properly initialized with tool_registry and llm_provider. Please ensure the tool registry is properly configured with provider references."
                )

            tool_registry = self.tool_registry
            llm_provider = self.llm_provider
            model = getattr(self, 'model', None)
            config_getter = getattr(tool_registry, "config_getter", None)

            # Create task ID for background execution
            task_id = str(uuid.uuid4())

            if runInBackground:
                # Run in background - non-blocking
                # Create background task
                bg_task = BackgroundAgentTask(
                    task_id=task_id,
                    agent_name=agent_name,
                    prompt=prompt,
                    status="pending",
                )

                async with _background_lock:
                    _background_agents[task_id] = bg_task

                # Create async task to run the agent
                async_task = asyncio.create_task(
                    _run_agent_in_background(
                        task_id=task_id,
                        agent_name=agent_name,
                        prompt=prompt,
                        llm_provider=llm_provider,
                        tool_registry=tool_registry,
                        model=model,
                        config_getter=config_getter,
                    )
                )

                # Store the task reference
                async with _background_lock:
                    if task_id in _background_agents:
                        _background_agents[task_id].task = async_task

                return ToolOutput(
                    success=True,
                    result=f"Background agent '{agent_name}' started. Task ID: {task_id}. Use agent_status tool to check progress and get results.",
                    metadata={
                        "agent": agent_name,
                        "task_id": task_id,
                        "status": "running",
                        "prompt_length": len(prompt),
                        "background": True
                    }
                )
            else:
                # Run synchronously (blocking) - for backwards compatibility
                from core.agents import EXPLORE, ExploreAgent, PLAN, PlanAgent
                from core.config.settings import Settings

                if agent_name == "explore":
                    def explore_config_getter() -> Settings:
                        if callable(config_getter):
                            base_settings = config_getter()
                        else:
                            base_settings = Settings()
                        merged_config = EXPLORE.apply_to_config(base_settings.model_dump())
                        return Settings(initial_config=merged_config)

                    explore_registry = _FilteredToolRegistry(
                        tool_registry,
                        allowed_tools=("read", "ls", "find", "grep"),
                        llm_provider=llm_provider,
                        model=model,
                        config_getter=explore_config_getter,
                    )

                    subagent = ExploreAgent(
                        llm_provider=llm_provider,
                        tool_registry=explore_registry,
                        model=model,
                        config_getter=explore_config_getter,
                    )
                    subagent.rebuild_system_prompt()

                    result = await subagent.process(prompt)

                    return ToolOutput(
                        success=True,
                        result=result,
                        metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                    )

                elif agent_name == "plan":
                    def plan_config_getter() -> Settings:
                        if callable(config_getter):
                            base_settings = config_getter()
                        else:
                            base_settings = Settings()
                        merged_config = PLAN.apply_to_config(base_settings.model_dump())
                        return Settings(initial_config=merged_config)

                    plan_registry = _FilteredToolRegistry(
                        tool_registry,
                        allowed_tools=("read", "ls", "find", "grep", "web_search", "fetch_webpage", "save_memory", "read_memory"),
                        llm_provider=llm_provider,
                        model=model,
                        config_getter=plan_config_getter,
                    )

                    subagent = PlanAgent(
                        llm_provider=llm_provider,
                        tool_registry=plan_registry,
                        model=model,
                        config_getter=plan_config_getter,
                    )
                    subagent.rebuild_system_prompt()

                    result = await subagent.process(prompt)

                    return ToolOutput(
                        success=True,
                        result=result,
                        metadata={"agent": agent_name, "prompt_length": len(prompt), "background": False}
                    )

                else:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error=f"Unknown agent: {agent_name}. Available agents: 'explore', 'plan'"
                    )

        except ImportError as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to import agent classes: {str(e)}. Please ensure the agent modules are properly installed and accessible."
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to invoke agent: {str(e)}. Please check if the agent configuration is correct and if the required dependencies are available."
            )


class AgentStatusTool(BaseTool):
    """Tool for checking status and output of background agents"""

    name = "agent_status"
    description = """Check status and retrieve output from background agent tasks.

Parameters:
- taskId (required): Background task ID from agents tool, or 'list' to see all tasks

Returns task status (pending/running/completed/failed), output, errors, and metadata.
Do other work before checking status again on running tasks."""
    input_schema = {
        "type": "object",
        "properties": {
            "taskId": {
                "type": "string",
                "description": "Task ID of the background agent to check. Use 'list' to see all background agents.",
                "minLength": 1
            }
        },
        "required": ["taskId"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support camelCase parameter names
        taskId = self._get_param(input_data, "taskId")

        if not isinstance(taskId, str) or not taskId:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid taskId: must be a non-empty string. Use 'list' to see all background agents."
            )

        try:
            if taskId.lower() == "list":
                # List all background agents
                agents = await list_background_agents()
                if not agents:
                    return ToolOutput(
                        success=True,
                        result="No background agents running.",
                        metadata={"count": 0}
                    )

                # Format list
                lines = [f"Total background agents: {len(agents)}\n"]
                for agent in agents:
                    lines.append(
                        f"- Task ID: {agent.task_id}\n"
                        f"  Agent: {agent.agent_name}\n"
                        f"  Status: {agent.status}\n"
                        f"  Created: {agent.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    if agent.completed_at:
                        lines.append(f"  Completed: {agent.completed_at.strftime('%Y-%m-%d %H:%M:%S')}\n")

                return ToolOutput(
                    success=True,
                    result="\n".join(lines),
                    metadata={"count": len(agents), "agents": [
                        {"taskId": a.task_id, "agent": a.agent_name, "status": a.status}
                        for a in agents
                    ]}
                )

            # Get specific agent status
            agent = await get_background_agent(taskId)
            if not agent:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Task ID '{taskId}' not found. Use 'list' to see available background agents."
                )

            # Format the response based on status
            if agent.status == "completed":
                result_text = f"Background agent completed!\n\nOutput:\n{agent.result}"
            elif agent.status == "failed":
                result_text = f"Background agent failed!\n\nError: {agent.error}"
            elif agent.status == "running":
                result_text = f"Background agent is still running...\n\nTask: {agent.prompt[:100]}...\n\nIMPORTANT: Do NOT check status again immediately. Do OTHER meaningful work first (read files, search patterns, etc.) before checking again. Check status only when you actually need the result or have completed other tasks."
            else:
                result_text = f"Background agent status: {agent.status}\n\nDo other work before checking again."

            return ToolOutput(
                success=True,
                result=result_text,
                metadata={
                    "task_id": agent.task_id,
                    "agent": agent.agent_name,
                    "status": agent.status,
                    "prompt": agent.prompt,
                    "result": agent.result if agent.status == "completed" else None,
                    "error": agent.error if agent.status == "failed" else None,
                    "created_at": agent.created_at.isoformat(),
                    "completed_at": agent.completed_at.isoformat() if agent.completed_at else None,
                }
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to get agent status: {str(e)}"
            )
