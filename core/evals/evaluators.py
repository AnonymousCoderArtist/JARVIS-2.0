"""Evaluators for JARVIS responses"""

from dataclasses import dataclass
from typing import Any

from .metrics import EvalMetrics, MetricsCollector


@dataclass
class EvalConfig:
    """Configuration for evaluators"""
    measure_latency: bool = True
    measure_cost: bool = True
    measure_energy: bool = False
    track_tokens: bool = True


class ResponseEvaluator:
    """Evaluates agent responses"""

    def __init__(self, config: EvalConfig | None = None):
        self.config = config or EvalConfig()
        self.collector = MetricsCollector()

    async def evaluate(
        self,
        query: str,
        response: str,
        tool_calls: list[dict] | None = None,
        model: str | None = None,
    ) -> EvalMetrics:
        """Evaluate a single response."""
        self.collector.start_timer()

        metrics = EvalMetrics()

        # Estimate token count (rough approximation)
        if self.config.track_tokens:
            input_tokens = len(query.split()) * 1.3
            output_tokens = len(response.split()) * 1.3
            metrics.token_count = int(input_tokens + output_tokens)

        # Estimate cost (rough approximation)
        if self.config.measure_cost:
            cost_per_1k = 0.001  # Default cheap model rate
            metrics.cost_usd = (metrics.token_count / 1000) * cost_per_1k

        # Measure latency
        if self.config.measure_latency:
            metrics.latency_ms = self.collector.stop_timer(
                token_count=metrics.token_count,
                cost_usd=metrics.cost_usd,
            ).latency_ms
        else:
            self.collector.stop_timer()

        metrics.success = True
        return metrics

    def get_recent_metrics(self, n: int = 10) -> list[EvalMetrics]:
        """Get recent metrics."""
        return self.collector.metrics[-n:]


class ToolEvaluator:
    """Evaluates tool usage efficiency"""

    def __init__(self):
        self.tool_stats: dict[str, dict[str, Any]] = {}

    def record_tool(self, tool_name: str, duration_ms: float, success: bool):
        """Record a tool usage."""
        if tool_name not in self.tool_stats:
            self.tool_stats[tool_name] = {
                "count": 0,
                "total_time_ms": 0,
                "successes": 0,
                "failures": 0,
            }

        stats = self.tool_stats[tool_name]
        stats["count"] += 1
        stats["total_time_ms"] += duration_ms
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

    def get_tool_stats(self, tool_name: str) -> dict[str, Any]:
        """Get statistics for a tool."""
        return self.tool_stats.get(tool_name, {})

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get all tool statistics."""
        result = {}
        for name, stats in self.tool_stats.items():
            avg_time = stats["total_time_ms"] / stats["count"] if stats["count"] > 0 else 0
            success_rate = stats["successes"] / stats["count"] if stats["count"] > 0 else 0
            result[name] = {
                "count": stats["count"],
                "avg_time_ms": avg_time,
                "success_rate": success_rate,
            }
        return result
