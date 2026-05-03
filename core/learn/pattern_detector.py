"""Pattern detector for identifying user preferences and behaviors"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectedPattern:
    """A pattern detected from user interactions"""
    name: str
    category: str  # "preference", "behavior", "optimization"
    confidence: float
    evidence: list[str]
    suggestion: str


class PatternDetector:
    """Detects patterns in user interactions to inform learning"""

    # Query type patterns
    QUERY_PATTERNS = {
        "code_review": [r"review", r"check", r"analyze", r"inspection"],
        "bug_fix": [r"fix", r"bug", r"error", r"issue", r"broken"],
        "implementation": [r"implement", r"create", r"build", r"develop"],
        "refactor": [r"refactor", r"restructure", r"clean", r"optimize"],
        "documentation": [r"document", r"readme", r"comment", r"explain"],
        "testing": [r"test", r"spec", r"coverage", r"assert"],
    }

    # Context preference patterns
    CONTEXT_PATTERNS = {
        "prefers_specific_files": [r"file:\s*(\S+)", r"in\s+(\S+\.\w+)"],
        "wants_code_only": [r"just the code", r"code only", r"no explanation"],
        "needs_explanation": [r"explain", r"how", r"why", r"because"],
    }

    def __init__(self):
        self.detected_patterns: list[DetectedPattern] = []

    def detect_from_input(self, user_input: str, agent_response: str) -> list[DetectedPattern]:
        """Detect patterns from a user-agent interaction"""
        patterns = []

        # Detect query type
        query_type = self._detect_query_type(user_input)
        if query_type:
            patterns.append(DetectedPattern(
                name=f"query_type_{query_type}",
                category="behavior",
                confidence=0.9,
                evidence=[user_input[:100]],
                suggestion=f"For {query_type} queries, consider using specialized tools"
            ))

        # Detect context preferences
        context_prefs = self._detect_context_preferences(user_input)
        patterns.extend(context_prefs)

        # Detect tool usage patterns
        tool_patterns = self._detect_tool_patterns(user_input, agent_response)
        patterns.extend(tool_patterns)

        self.detected_patterns.extend(patterns)
        return patterns

    def _detect_query_type(self, user_input: str) -> str | None:
        """Detect the type of query"""
        user_lower = user_input.lower()
        for qtype, patterns in self.QUERY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, user_lower):
                    return qtype
        return None

    def _detect_context_preferences(self, user_input: str) -> list[DetectedPattern]:
        """Detect context and formatting preferences"""
        patterns = []
        user_lower = user_input.lower()

        # Check for code-only preference
        if any(p in user_lower for p in ["just the code", "code only", "no explanation"]):
            patterns.append(DetectedPattern(
                name="code_only_output",
                category="preference",
                confidence=0.95,
                evidence=[user_input[:100]],
                suggestion="Return only code without explanation when this pattern is detected"
            ))

        # Check for explanation preference
        if any(p in user_lower for p in ["explain", "how does this work", "why"]):
            patterns.append(DetectedPattern(
                name="wants_explanation",
                category="preference",
                confidence=0.9,
                evidence=[user_input[:100]],
                suggestion="Include detailed explanations with code examples"
            ))

        return patterns

    def _detect_tool_patterns(self, user_input: str, agent_response: str) -> list[DetectedPattern]:
        """Detect tool usage patterns from interaction"""
        patterns = []

        # Check if tools were used
        if "Tool calls:" in agent_response or "toolCalls" in agent_response:
            # Extract tool names
            tool_names = re.findall(r'"name":\s*"(\w+)"', agent_response)
            if tool_names:
                patterns.append(DetectedPattern(
                    name="tool_usage_detected",
                    category="optimization",
                    confidence=0.85,
                    evidence=[f"Used tools: {', '.join(tool_names)}"],
                    suggestion="Consider pre-loading tools for similar queries"
                ))

        return patterns

    def get_learned_preferences(self) -> dict[str, Any]:
        """Get aggregated learned preferences"""
        preferences = {
            "preferred_output_format": "code_with_explanation",
            "preferred_tools": [],
            "query_type_routing": {},
            "context_awareness": True
        }

        for pattern in self.detected_patterns:
            if pattern.name == "code_only_output":
                preferences["preferred_output_format"] = "code_only"
            elif pattern.name == "wants_explanation":
                preferences["preferred_output_format"] = "code_with_explanation"

        return preferences