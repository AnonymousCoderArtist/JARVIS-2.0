"""Tool for reading watcher status and Common Operational Picture (COP) data"""

import json
from pathlib import Path
from typing import Any
from .base import BaseTool, ToolInput, ToolOutput

class WatcherStatusTool(BaseTool):
    """Tool for reading the status of passive watchers and COP data"""
    
    name = "watcher_status"
    description = """Read the status of passive watchers and data from the Common Operational Picture (COP).
Use this to get real-time intelligence data updated by background watchers (e.g., world intelligence, system health)."""
    
    input_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The COP key to read (e.g., 'WorldMonitorWatcher'). If omitted, lists all available keys."
            },
            "offset": {
                "type": "integer",
                "description": "Number of lines to skip from the beginning of the file.",
                "default": 0
            },
            "limit": {
                "type": "integer",
                "description": "Number of entries to read. If 0 or omitted, reads all remaining lines.",
                "default": 0
            }
        }
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        key = getattr(input_data, "key", None)
        offset = getattr(input_data, "offset", 0)
        limit = getattr(input_data, "limit", 0)
        
        cop_dir = Path(".jarvis") / "status"
        
        if not cop_dir.exists():
            return ToolOutput(success=True, result="No watcher data available yet.")
            
        if key:
            cop_file = cop_dir / f"{key}.cop.jsonl"
            if not cop_file.exists():
                return ToolOutput(success=False, error=f"COP key '{key}' not found.")
                
            try:
                entries = []
                with open(cop_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    
                    # Apply pagination logic
                    target_lines = lines[offset:]
                    if limit > 0:
                        target_lines = target_lines[:limit]
                        
                    for line in target_lines:
                        if line.strip():
                            entries.append(json.loads(line))
                            
                return ToolOutput(success=True, result={"total_lines": len(lines), "entries": entries})
            except Exception as e:
                return ToolOutput(success=False, error=f"Failed to read COP key '{key}': {str(e)}")
        else:
            keys = [f.name.replace(".cop.jsonl", "") for f in cop_dir.glob("*.cop.jsonl")]
            if not keys:
                return ToolOutput(success=True, result="No COP keys available.")
            return ToolOutput(success=True, result={"available_keys": keys})
