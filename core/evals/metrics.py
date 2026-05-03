"""Evaluation metrics for JARVIS"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalMetrics:
    """Evaluation metrics for a single operation"""
    latency_ms: float = 0.0
    token_count: int = 0
    cost_usd: float = 0.0
    energy_joules: float = 0.0
    flops: int = 0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "token_count": self.token_count,
            "cost_usd": self.cost_usd,
            "energy_joules": self.energy_joules,
            "flops": self.flops,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class EvalResult:
    """Complete evaluation result"""
    metrics: EvalMetrics
    trace: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.metrics, dict):
            self.metrics = EvalMetrics(**self.metrics)  # type: ignore


class MetricsCollector:
    """Collects and aggregates metrics"""

    def __init__(self):
        self.metrics: list[EvalMetrics] = []
        self._start_time: float | None = None

    def start_timer(self) -> None:
        self._start_time = time.perf_counter()

    def stop_timer(self, token_count: int = 0, cost_usd: float = 0.0) -> EvalMetrics:
        if self._start_time is None:
            return EvalMetrics()

        elapsed = (time.perf_counter() - self._start_time) * 1000
        self._start_time = None

        metrics = EvalMetrics(
            latency_ms=elapsed,
            token_count=token_count,
            cost_usd=cost_usd,
        )
        self.metrics.append(metrics)
        return metrics

    def get_aggregate(self) -> dict[str, float]:
        if not self.metrics:
            return {
                "avg_latency_ms": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "success_rate": 0,
            }

        return {
            "avg_latency_ms": sum(m.latency_ms for m in self.metrics) / len(self.metrics),
            "total_tokens": sum(m.token_count for m in self.metrics),
            "total_cost_usd": sum(m.cost_usd for m in self.metrics),
            "success_rate": sum(1 for m in self.metrics if m.success) / len(self.metrics),
        }

    def reset(self) -> None:
        self.metrics.clear()