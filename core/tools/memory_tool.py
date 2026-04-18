"""Memory management tool"""

import json
from pathlib import Path

from .base import BaseTool, ToolInput, ToolOutput


class SaveMemoryTool(BaseTool):
    """Tool for saving facts/preferences across sessions"""

    name = "save_memory"
    description = "Saves concise user context (preferences, facts) for use across future sessions"
    input_schema = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The specific fact, preference, or piece of information to remember",
                "minLength": 1
            },
            "scope": {
                "type": "string",
                "enum": ["global", "project"],
                "description": "Scope for the memory: 'global' applies across all projects, 'project' is specific to this codebase",
                "default": "global"
            }
        },
        "required": ["fact"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        fact = getattr(input_data, "fact", None)
        scope = getattr(input_data, "scope", "global")

        try:
            # Determine storage location
            # In JARVIS, we might use a dedicated memory folder
            memory_dir = Path("core/memory/storage")
            memory_dir.mkdir(parents=True, exist_ok=True)

            memory_file = memory_dir / f"{scope}_memory.json"

            # Load existing memory
            memories = []
            if memory_file.exists():
                with open(memory_file, encoding='utf-8') as f:
                    memories = json.load(f)

            # Add new fact
            memories.append({
                "fact": fact,
                "timestamp": __import__("datetime").datetime.now().isoformat()
            })

            # Save back
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump(memories, f, indent=2)

            return ToolOutput(
                success=True,
                result=f"Fact remembered in {scope} scope: '{fact}'",
                metadata={"scope": scope, "fact_count": len(memories)}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to save memory: {str(e)}"
            )
