"""Reward functions for agent optimization"""

from dataclasses import dataclass
from typing import Any


@dataclass
class RewardConfig:
    """Configuration for reward calculation"""
    latency_weight: float = 0.1
    cost_weight: float = 0.2
    success_weight: float = 0.7
    energy_weight: float = 0.0
    flops_weight: float = 0.0


class RewardFunction:
    """Calculates rewards for agent actions"""

    def __init__(self, config: RewardConfig | None = None):
        self.config = config or RewardConfig()

    def calculate(self, metrics: dict[str, Any]) -> float:
        """Calculate reward based on metrics."""
        reward = 0.0

        # Success bonus
        if metrics.get("success", False):
            reward += self.config.success_weight

        # Latency penalty (lower is better)
        latency = metrics.get("latency_ms", 0)
        latency_score = max(0, 1 - (latency / 10000))  # Normalize against 10s
        reward += latency_score * self.config.latency_weight

        # Cost penalty (lower is better)
        cost = metrics.get("cost_usd", 0)
        cost_score = max(0, 1 - (cost / 10))  # Normalize against $10
        reward += cost_score * self.config.cost_weight

        # Energy penalty
        energy = metrics.get("energy_joules", 0)
        energy_score = max(0, 1 - (energy / 100000))  # Normalize
        reward += energy_score * self.config.energy_weight

        return reward

    def normalize_reward(self, reward: float, min_val: float = -1.0, max_val: float = 1.0) -> float:
        """Normalize reward to a range."""
        return max(min_val, min(max_val, reward))


class RouterPolicy:
    """Routes queries to appropriate handlers based on complexity"""

    def __init__(self):
        self.simple_patterns = ["hello", "hi", "help", "thanks", "thank you"]
        self.code_patterns = ["fix", "implement", "create", "write", "refactor"]
        self.research_patterns = ["research", "analyze", "compare", "summarize"]

    def route(self, query: str) -> str:
        """Route query to appropriate agent."""
        query_lower = query.lower()

        # Simple chat
        if any(p in query_lower for p in self.simple_patterns):
            return "simple_chat"

        # Code tasks
        if any(p in query_lower for p in self.code_patterns):
            return "coding"

        # Research tasks
        if any(p in query_lower for p in self.research_patterns):
            return "research"

        return "default"

    def get_expected_latency(self, route: str) -> float:
        """Get expected latency for route in ms."""
        expectations = {
            "simple_chat": 100,
            "coding": 500,
            "research": 2000,
            "default": 300,
        }
        return expectations.get(route, 300)
