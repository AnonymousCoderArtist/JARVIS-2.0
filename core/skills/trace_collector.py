"""Trace collection for skill optimization."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
import hashlib


@dataclass
class SkillTrace:
    """A single trace for skill optimization."""
    skill_name: str
    timestamp: float
    input: str
    output: str
    metrics: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillTrace:
        return cls(
            skill_name=data.get("skill_name", ""),
            timestamp=data.get("timestamp", 0.0),
            input=data.get("input", ""),
            output=data.get("output", ""),
            metrics=data.get("metrics", {}),
            success=data.get("success", True),
            error=data.get("error"),
        )


class TraceCollector:
    """Collects and manages traces for skill optimization."""
    
    def __init__(self, trace_dir: Path | None = None):
        self.trace_dir = trace_dir or Path.home() / ".jarvis" / "traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._current_traces: list[SkillTrace] = []
    
    def record_trace(self, trace: SkillTrace) -> None:
        """Record a single trace."""
        self._current_traces.append(trace)
        self._persist_trace(trace)
    
    def _persist_trace(self, trace: SkillTrace) -> None:
        """Persist trace to disk."""
        trace_file = self.trace_dir / f"{trace.skill_name}_traces.jsonl"
        
        with open(trace_file, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")
    
    def get_traces(self, skill_name: str | None = None, limit: int = 100) -> list[SkillTrace]:
        """Get traces, optionally filtered by skill name."""
        if skill_name:
            trace_file = self.trace_dir / f"{skill_name}_traces.jsonl"
            if not trace_file.exists():
                return []
            
            traces = []
            with open(trace_file) as f:
                for line in f:
                    if line.strip():
                        traces.append(SkillTrace.from_dict(json.loads(line)))
            return traces[-limit:]
        
        # Get all traces
        all_traces = []
        for trace_file in self.trace_dir.glob("*_traces.jsonl"):
            with open(trace_file) as f:
                for line in f:
                    if line.strip():
                        all_traces.append(SkillTrace.from_dict(json.loads(line)))
        
        return all_traces[-limit:]
    
    def clear_traces(self, skill_name: str | None = None) -> int:
        """Clear traces, optionally for a specific skill."""
        if skill_name:
            trace_file = self.trace_dir / f"{skill_name}_traces.jsonl"
            if trace_file.exists():
                count = len(trace_file.read_text().strip().split("\n"))
                trace_file.unlink()
                return count
            return 0
        
        count = 0
        for trace_file in self.trace_dir.glob("*_traces.jsonl"):
            count += len(trace_file.read_text().strip().split("\n"))
            trace_file.unlink()
        return count
    
    def get_trace_count(self, skill_name: str) -> int:
        """Get the number of traces for a skill."""
        trace_file = self.trace_dir / f"{skill_name}_traces.jsonl"
        if not trace_file.exists():
            return 0
        return len(trace_file.read_text().strip().split("\n"))


# Global trace collector instance
_trace_collector: TraceCollector | None = None


def get_trace_collector() -> TraceCollector:
    """Get the global trace collector instance."""
    global _trace_collector
    if _trace_collector is None:
        _trace_collector = TraceCollector()
    return _trace_collector