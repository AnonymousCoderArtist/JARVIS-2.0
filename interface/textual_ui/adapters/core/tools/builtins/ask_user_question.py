"""Ask user question adapter."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Choice:
    """Choice."""
    label: str
    description: str


@dataclass
class Question:
    """Question."""
    question: str
    choices: list[Choice]


@dataclass
class AskUserQuestionArgs:
    """Ask user question args."""
    question: str
    choices: list[dict[str, Any]]


@dataclass
class AskUserQuestionResult:
    """Ask user question result."""
    selected: str
