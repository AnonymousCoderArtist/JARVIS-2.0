"""Trace analyzer for OpenJarvis Spec-Level Distillation"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TraceMetrics:
    """Metrics extracted from trace data"""
    total_interactions: int = 0
    successful_traces: int = 0

class TraceAnalyzer:
    """Analyzes M1 session traces to prepare for M2 distillation and DSPy optimization"""

    def __init__(self, sessions_dir: str = ".jarvis/traces"):
        self.sessions_dir = Path(sessions_dir)

    async def analyze_sessions(self, limit: int = 100) -> TraceMetrics:
        """Analyze recent trace files and extract metrics"""
        if not self.sessions_dir.exists():
            return TraceMetrics()

        trace_files = sorted(
            self.sessions_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]

        total = 0
        success = 0

        for f_path in trace_files:
            with open(f_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        total += 1
                        if data.get("reward") or data.get("trajectory", {}).get("success"):
                            success += 1
                    except json.JSONDecodeError:
                        pass

        return TraceMetrics(total_interactions=total, successful_traces=success)

    async def extract_successful_tool_patterns(self) -> list[dict[str, Any]]:
        """Used by DSPy optimizer to find winning tool sequences"""
        patterns = []
        traces = await self.get_successful_traces()
        for trace in traces:
            # Simplified pattern extraction: just grab tool calls from the trajectory
            if "toolCalls" in trace:
                patterns.append({
                    "input": trace.get("user_input", ""),
                    "successful_sequence": [tc.get("function", {}).get("name") for tc in trace["toolCalls"]]
                })
        return patterns

    async def get_successful_traces(self) -> list[dict[str, Any]]:
        """Retrieve only the successful M1 traces for M2 dataset generation"""
        if not self.sessions_dir.exists():
            return []

        successful_traces = []
        for f_path in self.sessions_dir.glob("*.jsonl"):
            with open(f_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("reward") or data.get("trajectory", {}).get("success"):
                            successful_traces.append(data.get("trajectory", {}))
                    except json.JSONDecodeError:
                        pass
        return successful_traces
