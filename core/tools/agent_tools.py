"""Agent and Skill management tools"""

from .base import BaseTool, ToolInput, ToolOutput


class InvokeAgentTool(BaseTool):
    """Tool for invoking specialized agents"""

    name = "invoke_agent"
    description = "Invoke a specialized agent to perform a specific task or investigation"
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
                error="Invalid agent invocation input",
            )

        # This tool requires integration with the AgentCoordinator
        # In a real system, it would call coordinator.execute_task

        return ToolOutput(
            success=True,
            result=f"Invoked agent '{agent_name}' with prompt: {prompt[:50]}...",
            metadata={"agent": agent_name, "prompt_length": len(prompt)}
        )


class ActivateSkillTool(BaseTool):
    """Tool for activating specialized agent skills"""

    name = "activate_skill"
    description = "Activates a specialized agent skill by name to receive expert guidance"
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "enum": ["skill-creator", "reverse-engineering", "modern-python"],
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
                error="Invalid skill name",
            )

        # This tool would load specialized instructions for the agent

        return ToolOutput(
            success=True,
            result=f"Activated skill: {skill_name}. Specialized guidance is now active.",
            metadata={"skill": skill_name}
        )
