"""DSPy-style optimizer for JARVIS prompts"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DSPyConfig:
    """Configuration for DSPy optimization"""
    enabled: bool = True
    optimize_tools: bool = True
    optimize_prompts: bool = True
    generations: int = 3
    temperature: float = 0.7


class DSPyOptimizer:
    """DSPy-style teleprompter for optimizing tool usage and prompts"""

    def __init__(self, config: DSPyConfig | None = None):
        self.config = config or DSPyConfig()
        self.optimized_prompts: dict[str, str] = {}
        self.optimized_policies: dict[str, Any] = {}

    async def optimize_from_traces(
        self,
        traces: list[dict[str, Any]],
        base_prompt: str,
    ) -> str:
        """Optimize prompt from successful traces."""
        if not self.config.enabled or not traces:
            return base_prompt

        # Analyze successful traces
        successful = [t for t in traces if t.get("reward", False)]
        if not successful:
            return base_prompt

        # Extract patterns
        patterns = self._extract_patterns(successful)

        # Generate optimized prompt
        optimized = self._generate_optimized_prompt(base_prompt, patterns)
        self.optimized_prompts["latest"] = optimized

        return optimized

    def _extract_patterns(self, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract successful patterns from traces."""
        patterns = []
        for trace in traces:
            trajectory = trace.get("trajectory", {})
            tool_calls = trajectory.get("toolCalls", [])
            if tool_calls:
                patterns.append({
                    "input": trajectory.get("user_input", ""),
                    "tools": [tc.get("function", {}).get("name") for tc in tool_calls],
                    "success": trace.get("reward", False),
                })
        return patterns

    def _generate_optimized_prompt(self, base_prompt: str, patterns: list[dict]) -> str:
        """Generate optimized prompt from patterns."""
        # Count tool usage
        tool_counts: dict[str, int] = {}
        for p in patterns:
            for tool in p.get("tools", []):
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

        # Sort by frequency
        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        top_tools = [t[0] for t in sorted_tools[:5]]

        # Add tool preference to prompt
        optimized = base_prompt.rstrip()
        if top_tools:
            optimized += f"\n\nPreferred tools for similar tasks: {', '.join(top_tools)}."

        return optimized

    def save_optimization(self, path: Path) -> None:
        """Save optimized policies to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "prompts": self.optimized_prompts,
                "policies": self.optimized_policies,
            }, f, indent=2)

    def load_optimization(self, path: Path) -> None:
        """Load optimized policies from file."""
        if not path.exists():
            return

        with open(path) as f:
            data = json.load(f)
            self.optimized_prompts = data.get("prompts", {})
            self.optimized_policies = data.get("policies", {})
