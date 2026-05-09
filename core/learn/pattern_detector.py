"""Pattern detector for identifying user preferences and behaviors."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DetectedPattern:
    """A pattern detected from user interactions"""
    name: str
    category: str  # "preference", "behavior", "optimization"
    confidence: float
    evidence: list[str]
    suggestion: str


# Lazy imports - resolved at first use to avoid circular imports during training
_MODEL = None
_TOKENIZER = None
_MODEL_LOADED = False


def _load_classifier():
    """Lazy-load the fine-tuned transformer classifier."""
    global _MODEL, _TOKENIZER, _MODEL_LOADED
    if _MODEL_LOADED:
        return _MODEL, _TOKENIZER

    try:
        from .Classification.train_classifier import (
            ID_TO_LABEL, MODEL_DIR, predict as _predict, load_model, LABELS,
        )
        result = load_model()
        if result is not None:
            _MODEL, _TOKENIZER = result
            print(f"Loaded fine-tuned classifier from {MODEL_DIR}")
        else:
            _MODEL_LOADED = True  # Mark loaded even if no model, to avoid repeated attempts
            return None, None
    except Exception:
        _MODEL_LOADED = True
        return None, None

    _MODEL_LOADED = True
    return _MODEL, _TOKENIZER


class PatternDetector:
    """Detects patterns in user interactions using transformer classifier."""

    _instance = None

    def __new__(cls):
        """Singleton pattern for model sharing."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.detected_patterns: list[DetectedPattern] = []

    def detect_from_input(self, user_input: str, agent_response: str) -> list[DetectedPattern]:
        """Detect patterns from a user-agent interaction."""
        patterns = []

        # Detect query type using fine-tuned transformer
        model, tokenizer = _load_classifier()
        if model is not None and tokenizer is not None:
            try:
                from .Classification.train_classifier import predict as _predict
                query_type, confidence = _predict(model, tokenizer, user_input)
            except Exception:
                query_type = "unknown"
                confidence = 0.0
        else:
            query_type, confidence = self._rule_based_classify(user_input)

        if query_type != "unknown":
            patterns.append(DetectedPattern(
                name=f"query_type_{query_type}",
                category="behavior",
                confidence=confidence,
                evidence=[user_input[:100]],
                suggestion=f"For {query_type} queries, consider using specialized tools",
            ))

        # Detect context preferences
        context_prefs = self._detect_context_preferences(user_input)
        patterns.extend(context_prefs)

        # Detect tool usage patterns
        tool_patterns = self._detect_tool_patterns(user_input, agent_response)
        patterns.extend(tool_patterns)

        self.detected_patterns.extend(patterns)
        return patterns

    def _rule_based_classify(self, user_input: str) -> tuple[str, float]:
        """Fallback rule-based classification when no ML model is available."""
        lower = user_input.lower()
        # Simple keyword matching
        keywords = {
            "bug_fix": ["fix", "bug", "error", "crash", "broken", "repair", "resolve", "patch", "debug"],
            "code_review": ["review", "check", "audit", "analyze", "evaluate", "examine", "critique"],
            "implementation": ["implement", "build", "create", "add", "develop", "write"],
            "refactor": ["refactor", "restructure", "clean up", "optimize", "simplify", "improve"],
            "documentation": ["document", "explain", "readme", "guide", "tutorial", "write docs"],
            "testing": ["test", "validate", "verify", "coverage", "unit test", "integration test"],
        }
        scores = {}
        for label, kws in keywords.items():
            score = sum(1 for kw in kws if kw in lower)
            if score > 0:
                scores[label] = score

        if not scores:
            return "unknown", 0.0

        best = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = min(scores[best] / max(total, 1), 0.95)
        return best, confidence

    def _detect_context_preferences(self, user_input: str) -> list[DetectedPattern]:
        """Detect context and formatting preferences."""
        patterns = []
        user_lower = user_input.lower()

        # Check for code-only preference
        if any(p in user_lower for p in ["just the code", "code only", "no explanation"]):
            patterns.append(DetectedPattern(
                name="code_only_output",
                category="preference",
                confidence=0.95,
                evidence=[user_input[:100]],
                suggestion="Return only code without explanation when this pattern is detected",
            ))

        # Check for explanation preference
        if any(p in user_lower for p in ["explain", "how does this work", "why"]):
            patterns.append(DetectedPattern(
                name="wants_explanation",
                category="preference",
                confidence=0.9,
                evidence=[user_input[:100]],
                suggestion="Include detailed explanations with code examples",
            ))

        return patterns

    def _detect_tool_patterns(self, user_input: str, agent_response: str) -> list[DetectedPattern]:
        """Detect tool usage patterns from interaction."""
        patterns = []

        # Check if tools were used
        if "Tool calls:" in agent_response or "toolCalls" in agent_response:
            tool_names = re.findall(r'"name":\s*"(\w+)"', agent_response)
            if tool_names:
                patterns.append(DetectedPattern(
                    name="tool_usage_detected",
                    category="optimization",
                    confidence=0.85,
                    evidence=[f"Used tools: {', '.join(tool_names)}"],
                    suggestion="Consider pre-loading tools for similar queries",
                ))

        return patterns

    def get_learned_preferences(self) -> dict[str, Any]:
        """Get aggregated learned preferences."""
        preferences = {
            "preferred_output_format": "code_with_explanation",
            "preferred_tools": [],
            "query_type_routing": {},
            "context_awareness": True,
        }

        for pattern in self.detected_patterns:
            if pattern.name == "code_only_output":
                preferences["preferred_output_format"] = "code_only"
            elif pattern.name == "wants_explanation":
                preferences["preferred_output_format"] = "code_with_explanation"

        return preferences