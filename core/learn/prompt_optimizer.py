"""Prompt optimizer that uses learned patterns to improve prompts"""

import hashlib
from dataclasses import dataclass
from typing import Any

from .pattern_detector import DetectedPattern


@dataclass
class OptimizedPrompt:
    """An optimized prompt with reasoning"""
    original: str
    optimized: str
    changes: list[str]
    confidence: float


class PromptOptimizer:
    """Optimizes prompts based on learned patterns"""

    def __init__(self):
        self.optimization_history: list[OptimizedPrompt] = []

    def optimize(
        self,
        system_prompt: str,
        user_input: str,
        patterns: list[DetectedPattern],
        preferences: dict[str, Any]
    ) -> OptimizedPrompt | None:
        """Optimize a prompt based on detected patterns"""
        changes = []
        optimized = system_prompt
        confidence = 0.5

        # Apply code-only preference
        for pattern in patterns:
            if pattern.name == "code_only_output":
                optimized = self._apply_code_only_optimization(optimized, user_input)
                changes.append("Applied code-only output format")
                confidence = max(confidence, pattern.confidence)

        # Apply explanation preference
        if any(p.name == "wants_explanation" for p in patterns):
            optimized = self._apply_explanation_optimization(optimized)
            changes.append("Added explanation requirements")
            confidence = max(confidence, 0.8)

        # Apply tool preference
        preferred_tools = preferences.get("preferred_tools", [])
        if preferred_tools:
            optimized = self._apply_tool_preference(optimized, preferred_tools)
            changes.append(f"Prioritized tools: {', '.join(preferred_tools)}")
            confidence = max(confidence, 0.7)

        # Only return optimization if there were changes
        if not changes:
            return None

        result = OptimizedPrompt(
            original=system_prompt,
            optimized=optimized,
            changes=changes,
            confidence=confidence
        )

        self.optimization_history.append(result)
        return result

    def _apply_code_only_optimization(self, prompt: str, user_input: str) -> str:
        """Optimize for code-only output"""
        # Add instruction to be concise and code-focused
        if "be concise" not in prompt.lower():
            return prompt.rstrip() + "\n\nBe concise. Return code without extensive explanation unless asked."
        return prompt

    def _apply_explanation_optimization(self, prompt: str) -> str:
        """Optimize for detailed explanations"""
        if "explain your reasoning" not in prompt.lower():
            return prompt.rstrip() + "\n\nExplain your reasoning step by step."
        return prompt

    def _apply_tool_preference(self, prompt: str, tools: list[str]) -> str:
        """Optimize for specific tool usage"""
        tool_hint = f"\n\nWhen applicable, prefer using: {', '.join(tools)}."
        return prompt.rstrip() + tool_hint

    def get_cached_optimization(self, key: str) -> OptimizedPrompt | None:
        """Get a cached optimization by hash key"""
        for opt in self.optimization_history:
            opt_key = self._compute_key(opt.original)
            if opt_key == key:
                return opt
        return None

    def _compute_key(self, prompt: str) -> str:
        """Compute a hash key for a prompt"""
        return hashlib.md5(prompt.encode()).hexdigest()[:16]