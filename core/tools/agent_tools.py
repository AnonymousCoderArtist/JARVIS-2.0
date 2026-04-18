"""Agent and Skill management tools"""

from typing import Dict, List, Optional, Any
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
        agent_name = input_data.agent_name
        prompt = input_data.prompt
        
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
        skill_name = input_data.name
        
        # This tool would load specialized instructions for the agent
        
        return ToolOutput(
            success=True,
            result=f"Activated skill: {skill_name}. Specialized guidance is now active.",
            metadata={"skill": skill_name}
        )
