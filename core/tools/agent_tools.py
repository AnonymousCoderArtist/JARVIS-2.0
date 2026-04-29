"""Agent and Skill management tools"""

from .base import BaseTool, ToolInput, ToolOutput


class InvokeAgentTool(BaseTool):
    """Tool for invoking specialized agents (OpenClaude style)"""

    name = "invoke_agent"
    description = """Invoke a specialized agent to perform a specific task or investigation. Use this to delegate work to agents with specialized capabilities.

Usage:
- Specify the agent name to invoke (e.g., 'coding', 'knowledge')
- Provide a complete prompt describing the task for the subagent
- Use wait_for_previous to control execution timing
- Useful for delegating specialized work while maintaining context
- Use this for complex tasks that benefit from specialized agent expertise"""
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

        # This tool requires integration with the agent system
        # In a real system, it would call the appropriate agent

        return ToolOutput(
            success=True,
            result=f"Invoked agent '{agent_name}' with prompt: {prompt[:50]}...",
            metadata={"agent": agent_name, "prompt_length": len(prompt)}
        )


class ActivateSkillTool(BaseTool):
    """Tool for activating specialized agent skills (OpenClaude style)"""

    name = "activate_skill"
    description = """Activates a specialized agent skill by name to receive expert guidance. Use this to enhance agent capabilities with domain-specific expertise.

Usage:
- Specify the skill name to activate (e.g., 'skill-creator', 'reverse-engineering', 'modern-python')
- Skills provide specialized instructions and guidance for specific domains
- Useful for tasks requiring specialized knowledge or approaches
- Skills augment the agent's base capabilities with expert guidance
- Available skills are defined in the system configuration"""
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
