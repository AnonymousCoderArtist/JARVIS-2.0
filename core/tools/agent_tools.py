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
    from core.agents import EXPLORE, ExploreAgent
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
                allowed_tools=("read", "list_dir", "glob", "grep"),
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
        return """## Available Skills

Skills provide specialized domain expertise. ONLY activate skills when the task explicitly requires specialized knowledge.

**Available skills:**
- skill-creator: For creating new skills and modifying existing skill files
- reverse-engineering: For analyzing APIs, websites, and systems
- modern-python: For setting up Python projects and modern tooling

IMPORTANT: Only activate skills when the task clearly requires specialized expertise."""


class AgentsTool(BaseTool):
    """Tool for invoking specialized agents"""

    name = "agents"
    description = """Invoke a specialized subagent to perform a specific task or investigation. Use this to delegate work to agents with specialized capabilities.

Usage:
- Specify the agent name to invoke (e.g., 'explore' for codebase exploration and analysis)
- Provide a complete prompt describing the task for the subagent
- run_in_background parameter is REQUIRED - you must explicitly set it

Background Execution (run_in_background=true):
- Use ONLY when you have multiple independent tasks and can do other work while subagent runs
- The main agent continues working while subagent runs in background
- Use agent_status tool to check progress and get results
- Check completion only after doing other meaningful work

Foreground Execution (run_in_background=false):
- Use for single tasks when you need the result immediately
- Agent runs synchronously and returns result directly
- No need to check status - result is returned immediately

When to use which:
- Single task needing immediate result -> run_in_background=false
- Multiple tasks, can do other work while subagent runs -> run_in_background=true"""
    input_schema = {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Name of the specialized subagent to invoke (e.g., 'explore')",
                "minLength": 1
            },
            "prompt": {
                "type": "string",
                "description": "The complete query or task to send to the subagent",
                "minLength": 1
            },
            "run_in_background": {
                "type": "boolean",
                "description": "REQUIRED: Set to true ONLY when delegating multiple tasks and can do other work. Set to false for single tasks needing immediate result."
            }
        },
        "required": ["agent_name", "prompt", "run_in_background"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support both camelCase and snake_case parameter names
        agent_name = self._get_param(input_data, "agent_name", "agentName")
        prompt = self._get_param(input_data, "prompt")
        run_in_background = self._get_param(input_data, "run_in_background", "runInBackground") or False

        if not isinstance(agent_name, str) or not isinstance(prompt, str):
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid agent invocation input: agent_name and prompt must be non-empty strings. Please provide a valid agent name and a descriptive task prompt."
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

            if run_in_background:
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
                from core.agents import EXPLORE, ExploreAgent
                from core.config.settings import Settings

                def explore_config_getter() -> Settings:
                    if callable(config_getter):
                        base_settings = config_getter()
                    else:
                        base_settings = Settings()
                    merged_config = EXPLORE.apply_to_config(base_settings.model_dump())
                    return Settings(initial_config=merged_config)

                explore_registry = _FilteredToolRegistry(
                    tool_registry,
                    allowed_tools=("read", "list_dir", "glob", "grep"),
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


class ActivateSkillTool(BaseTool):
    """Tool for activating specialized agent skills"""

    name = "activate_skill"
    description = get_skill_description()
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the specialized skill to activate for expert guidance"
            }
        },
        "required": ["name"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support both camelCase and snake_case parameter names
        skill_name = self._get_param(input_data, "name", "skill_name")

        if not isinstance(skill_name, str) or not skill_name:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid skill name: skill name must be a non-empty string. Please provide a valid skill name."
            )

        # Use SkillManager to activate the skill
        try:
            from core.skills import SkillManager
            skill_manager = SkillManager()
            success, message, content = skill_manager.activate_skill(skill_name)

            if not success:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=message
                )

            # Store skill content in the tool registry's context for the agent to access
            if self.tool_registry and hasattr(self.tool_registry, 'active_skills'):
                self.tool_registry.active_skills[skill_name] = content or ""

            return ToolOutput(
                success=True,
                result=message,
                metadata={"skill": skill_name, "content_length": len(content) if content else 0}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to activate skill: {str(e)}. Please check if the skill system is properly configured."
            )


class AgentStatusTool(BaseTool):
    """Tool for checking status and output of background agents"""

    name = "agent_status"
    description = """Check the status and output of a background agent task.

Usage:
- Provide a task_id to check the status of a specific background agent
- Use 'list' as task_id to see all running background agents
- Get the task_id from the response when starting a background agent
- Returns status (pending, running, completed, failed), output, and errors

The main agent will be automatically notified when background agents complete."""
    input_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID of the background agent to check. Use 'list' to see all background agents.",
                "minLength": 1
            }
        },
        "required": ["task_id"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Support both camelCase and snake_case parameter names
        task_id = self._get_param(input_data, "task_id", "taskId")

        if not isinstance(task_id, str) or not task_id:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid task_id: must be a non-empty string. Use 'list' to see all background agents."
            )

        try:
            if task_id.lower() == "list":
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
                        {"task_id": a.task_id, "agent": a.agent_name, "status": a.status}
                        for a in agents
                    ]}
                )

            # Get specific agent status
            agent = await get_background_agent(task_id)
            if not agent:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Task ID '{task_id}' not found. Use 'list' to see available background agents."
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
