"""Pattern detector for identifying user preferences and behaviors."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Import training components
from .Classification.train_classifier import (
    ID_TO_LABEL,
    MODEL_DIR,
    predict,
    load_model,
    LABELS,
)


@dataclass
class DetectedPattern:
    """A pattern detected from user interactions"""
    name: str
    category: str  # "preference", "behavior", "optimization"
    confidence: float
    evidence: list[str]
    suggestion: str


class PatternDetector:
    """Detects patterns in user interactions using transformer classifier."""

    _instance = None
    _model = None
    _tokenizer = None
    _model_loaded = False

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
        self._load_model()

    def _load_model(self) -> None:
        """Load the fine-tuned transformer classifier."""
        if PatternDetector._model_loaded:
            return

        result = load_model()
        if result is not None:
            PatternDetector._model, PatternDetector._tokenizer = result
            print(f"Loaded fine-tuned classifier from {MODEL_DIR}")
        else:
            raise RuntimeError(
                "No trained model found. Please run: "
                "python -m core.learn.Classification.train_classifier"
            )

        PatternDetector._model_loaded = True

    def detect_from_input(self, user_input: str, agent_response: str) -> list[DetectedPattern]:
        """Detect patterns from a user-agent interaction."""
        patterns = []

        # Detect query type using fine-tuned transformer
        try:
            query_type, confidence = predict(
                PatternDetector._model,
                PatternDetector._tokenizer,
                user_input,
            )
        except Exception as e:
            raise RuntimeError(f"Classification failed: {e}")

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