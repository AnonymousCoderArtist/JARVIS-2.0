"""Agent and Skill management tools"""

from __future__ import annotations

from collections.abc import Iterable

from .base import BaseTool, ToolInput, ToolOutput


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
- Use wait_for_previous to control execution timing
- Useful for delegating specialized work while maintaining context
- Use this for complex tasks that benefit from specialized agent expertise
- The explore subagent specializes in codebase exploration, architecture analysis, and finding specific patterns
- Subagents use the same model as the main agent for consistency"""
    input_schema = {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Name of the specialized subagent to invoke",
                "minLength": 1
            },
            "prompt": {
                "type": "string",
                "description": "The complete query or task to send to the subagent",
                "minLength": 1
            },
            "wait_for_previous": {
                "type": "boolean",
                "description": "Whether to wait for previous tool executions to complete before invoking",
                "default": True
            }
        },
        "required": ["agent_name", "prompt"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        agent_name = getattr(input_data, "agent_name", None)
        prompt = getattr(input_data, "prompt", None)

        if not isinstance(agent_name, str) or not isinstance(prompt, str):
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid agent invocation input: agent_name and prompt must be non-empty strings. Please provide a valid agent name and a descriptive task prompt."
            )

        # Import here to avoid circular dependencies
        try:
            from core.agents import EXPLORE, ExploreAgent
            from core.config.settings import Settings

            # Get the tool registry and LLM provider from the tool's context
            # This requires the tool to have access to these, which should be set up during initialization
            # For now, we'll need to make these accessible

            # Check if the tool has access to the registry and provider
            if not hasattr(self, 'tool_registry') or not hasattr(self, 'llm_provider'):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Agent tool not properly initialized with tool_registry and llm_provider. Please ensure the tool registry is properly configured with provider references."
                )

            tool_registry = self.tool_registry
            llm_provider = self.llm_provider

            # Get the model from the parent agent if available
            model = getattr(self, 'model', None)

            # Capture the current config getter if the registry has one.
            config_getter = getattr(tool_registry, "config_getter", None)

            def explore_config_getter() -> Settings:
                """Return the active config with the Explore profile overrides applied."""
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

            # Create the appropriate subagent
            if agent_name == "explore":
                subagent = ExploreAgent(
                    llm_provider=llm_provider,
                    tool_registry=explore_registry,
                    model=model,
                    config_getter=explore_config_getter,
                )

                # Rebuild system prompt with current tool descriptions
                subagent.rebuild_system_prompt()

                # Execute the task
                result = await subagent.process(prompt)

                return ToolOutput(
                    success=True,
                    result=result,
                    metadata={"agent": agent_name, "prompt_length": len(prompt)}
                )
            else:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Unknown subagent: {agent_name}. Available subagents: explore. Please use a valid subagent name."
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

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        skill_name = getattr(input_data, "name", None)

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
