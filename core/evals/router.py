"""Query router for JARVIS - routes queries to appropriate handlers"""

from dataclasses import dataclass
from typing import Any


@dataclass
class RouteConfig:
    """Configuration for routing"""
    simple_threshold_ms: float = 200
    research_threshold_ms: float = 2000
    use_routing: bool = True


class QueryRouter:
    """Routes queries to appropriate handlers based on complexity and type"""

    def __init__(self, config: RouteConfig | None = None):
        self.config = config or RouteConfig()
        self.simple_patterns = [
            "hello", "hi", "hey", "thanks", "thank you", "please",
            "help me", "how are", "what is", "who is", "when is"
        ]
        self.code_patterns = [
            "fix", "implement", "create", "write", "refactor", "debug",
            "code", "function", "class", "method", "variable", "error"
        ]
        self.research_patterns = [
            "research", "analyze", "compare", "summarize", "explain",
            "why", "how does", "impact", "trend", "study"
        ]

    def route(self, query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Route a query to the appropriate handler.

        Returns:
            Dict with route info: {"handler": str, "confidence": float, "expected_latency_ms": float}
        """
        query_lower = query.lower().strip()

        # Check simple chat patterns
        for pattern in self.simple_patterns:
            if pattern in query_lower:
                return {
                    "handler": "simple_chat",
                    "confidence": 0.9,
                    "expected_latency_ms": self.config.simple_threshold_ms,
                }

        # Check code patterns
        for pattern in self.code_patterns:
            if pattern in query_lower:
                return {
                    "handler": "coding",
                    "confidence": 0.85,
                    "expected_latency_ms": 500,
                }

        # Check research patterns
        for pattern in self.research_patterns:
            if pattern in query_lower:
                return {
                    "handler": "research",
                    "confidence": 0.8,
                    "expected_latency_ms": self.config.research_threshold_ms,
                }

        # Default route
        return {
            "handler": "default",
            "confidence": 0.5,
            "expected_latency_ms": 300,
        }

    def should_use_streaming(self, route: dict[str, Any]) -> bool:
        """Determine if streaming should be used based on route."""
        return route["handler"] == "research"
