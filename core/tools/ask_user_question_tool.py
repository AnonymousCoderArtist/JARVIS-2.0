"""AskUserQuestionTool - Ask multiple choice questions to the user"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field, field_validator

from core.tools.base import BaseTool, ToolInput, ToolOutput
from core.tools.permissions import PermissionContext, ToolPermission


# ============== Schemas ==============

class QuestionOptionSchema(BaseModel):
    """Schema for a single option in a multiple choice question."""
    label: str = Field(
        description="The display text for this option that the user will see and select. "
                   "Should be concise (1-5 words) and clearly describe the choice."
    )
    description: str = Field(
        description="Explanation of what this option means or what will happen if chosen. "
                   "Useful for providing context about trade-offs or implications."
    )
    preview: str | None = Field(
        default=None,
        description="Optional preview content rendered when this option is focused. "
                   "Use for mockups, code snippets, or visual comparisons."
    )


class QuestionSchema(BaseModel):
    """Schema for a single question."""
    question: str = Field(
        description="The complete question to ask the user. Should be clear, specific, "
                    "and end with a question mark."
    )
    header: str = Field(
        description="Very short label displayed as a chip/tag (max 12 chars). "
                    "Examples: 'Auth method', 'Library', 'Approach'.",
        max_length=12
    )
    options: list[QuestionOptionSchema] = Field(
        description="The available choices for this question. Must have 2-4 options. "
                    "Each option should be a distinct, mutually exclusive choice "
                    "(unless multiSelect is enabled).",
        min_length=2,
        max_length=4
    )
    multiSelect: bool = Field(
        default=False,
        description="Set to true to allow the user to select multiple options instead of just one."
    )


class AnnotationSchema(BaseModel):
    """Schema for annotations (notes on user selections)."""
    preview: str | None = Field(
        default=None,
        description="The preview content of the selected option, if the question used previews."
    )
    notes: str | None = Field(
        default=None,
        description="Free-text notes the user added to their selection."
    )


class AskUserInputSchema(BaseModel):
    """Input schema for AskUserQuestion tool."""
    questions: list[QuestionSchema] = Field(
        description="Questions to ask the user (1-4 questions)",
        min_length=1,
        max_length=4
    )
    answers: dict[str, str] | None = Field(
        default=None,
        description="User answers collected by the permission component"
    )
    annotations: dict[str, AnnotationSchema] | None = Field(
        default=None,
        description="Optional per-question annotations from the user (e.g., notes on preview selections). "
                    "Keyed by question text."
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Optional metadata for tracking and analytics purposes. "
                    "Not displayed to user."
    )

    @field_validator('questions')
    @classmethod
    def validate_unique_questions(cls, v: list[QuestionSchema]) -> list[QuestionSchema]:
        """Ensure question texts and option labels are unique."""
        questions = [q.question for q in v]
        if len(questions) != len(set(questions)):
            raise ValueError("Question texts must be unique")
        for question in v:
            labels = [opt.label for opt in question.options]
            if len(labels) != len(set(labels)):
                raise ValueError("Option labels must be unique within each question")
        return v


class AskUserOutputSchema(BaseModel):
    """Output schema for AskUserQuestion tool."""
    questions: list[QuestionSchema] = Field(
        description="The questions that were asked"
    )
    answers: dict[str, str] = Field(
        description="The answers provided by the user (question text -> answer string; "
                    "multi-select answers are comma-separated)"
    )
    annotations: dict[str, AnnotationSchema] | None = Field(
        default=None,
        description="Optional annotations from the user"
    )


# ============== Constants ==============

ASK_USER_QUESTION_TOOL_NAME = "AskUserQuestion"
ASK_USER_QUESTION_TOOL_CHIP_WIDTH = 12

DESCRIPTION = (
    "Asks the user multiple choice questions to gather information, clarify ambiguity, "
    "understand preferences, make decisions or offer them choices."
)

ASK_USER_QUESTION_TOOL_PROMPT = """Use this tool when you need to ask the user questions during execution. This allows you to:
1. Gather user preferences or requirements
2. Clarify ambiguous instructions
3. Get decisions on implementation choices as you work
4. Offer choices to the user about what direction to take.

Usage notes:
- Users will always be able to select "Other" to provide custom text input
- Use multiSelect: true to allow multiple answers to be selected for a question
- If you recommend a specific option, make that the first option in the list and add "(Recommended)" at the end of the label

IMPORTANT: Do not reference "the plan" in your questions because the user cannot see the plan in the UI until you finalize it. Use appropriate tool for plan approval.
"""

PREVIEW_FEATURE_PROMPT = """
Preview feature:
Use the optional `preview` field on options when presenting concrete artifacts that users need to visually compare:
- ASCII mockups of UI layouts or components
- Code snippets showing different implementations
- Diagram variations
- Configuration examples

Preview content is rendered in a side-by-side layout. Do not use previews for simple preference questions.
Note: previews are only supported for single-select questions (not multiSelect).
"""


# ============== Tool Implementation ==============

class AskUserQuestionTool(BaseTool):
    """Tool for asking multiple-choice questions to the user.

    This tool enables JARVIS to engage in interactive dialogues with users,
    gathering preferences, clarifying ambiguous instructions, and making
    collaborative decisions.
    """

    name: str = ASK_USER_QUESTION_TOOL_NAME
    description: str = DESCRIPTION
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The complete question to ask the user. Should be clear, specific, "
                                        "and end with a question mark."
                        },
                        "header": {
                            "type": "string",
                            "description": "Very short label displayed as a chip/tag (max 12 chars). "
                                        "Examples: 'Auth method', 'Library', 'Approach'.",
                            "maxLength": 12
                        },
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "The display text for this option that the user will see "
                                                    "and select. Should be concise (1-5 words)."
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Explanation of what this option means or what will happen "
                                                    "if chosen."
                                    },
                                    "preview": {
                                        "type": "string",
                                        "description": "Optional preview content for visual comparison."
                                    }
                                },
                                "required": ["label", "description"]
                            },
                            "minItems": 2,
                            "maxItems": 4
                        },
                        "multiSelect": {
                            "type": "boolean",
                            "description": "Set to true to allow the user to select multiple options."
                        }
                    },
                    "required": ["question", "header", "options"]
                },
                "minItems": 1,
                "maxItems": 4
            },
            "answers": {
                "type": "object",
                "description": "User answers collected by the permission component"
            },
            "annotations": {
                "type": "object",
                "description": "Optional per-question annotations from the user"
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata for tracking (e.g., source identifier)"
            }
        },
        "required": ["questions"]
    }

    def __init__(self, tool_registry=None, llm_provider=None, model=None):
        super().__init__(tool_registry, llm_provider, model)
        self._user_response_event: asyncio.Event | None = None
        self._user_response_data: dict | None = None

    def set_user_response(self, answers: dict[str, str], annotations: dict | None = None):
        """Set the user response (called by TUI when user answers)."""
        self._user_response_data = {"answers": answers, "annotations": annotations}
        if self._user_response_event:
            self._user_response_event.set()

    def reset_response_state(self):
        """Reset the response state for next question."""
        self._user_response_event = None
        self._user_response_data = None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """
        Execute the AskUserQuestion tool.

        This tool requires user interaction. In TUI mode, it displays questions
        and waits for user input. In CLI mode, it falls back to text-based input.
        """
        # Extract questions from input - handle both direct list and nested dict format
        raw_questions = getattr(input_data, "questions", None)
        
        # Handle different input formats
        if raw_questions is None:
            # Try to get from dict-style input (when LLM passes as function arguments)
            raw_questions = getattr(input_data, "questions", []) or getattr(input_data, "questions", None)
            if raw_questions is None:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="No questions provided"
                )
        
        # If questions is a dict with a 'questions' key, extract the list
        if isinstance(raw_questions, dict):
            if "questions" in raw_questions:
                questions = raw_questions["questions"]
            else:
                # It's a single question dict, wrap it in a list
                questions = [raw_questions]
        elif isinstance(raw_questions, list):
            questions = raw_questions
        else:
            return ToolOutput(
                success=False,
                result=None,
                error="Invalid questions format"
            )
        
        if not questions:
            return ToolOutput(
                success=False,
                result=None,
                error="No questions provided"
            )

        # Validate input schema - convert dicts to proper schema objects
        try:
            # Convert list of dicts to list of QuestionSchema objects
            validated_questions = []
            for q in questions:
                if isinstance(q, dict):
                    validated_questions.append(QuestionSchema(**q))
                else:
                    validated_questions.append(q)
            
            validated_input = AskUserInputSchema(questions=validated_questions)
        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Invalid input: {str(e)}"
            )

        # Check if we have pre-existing answers (from permission component)
        # Handle both direct dict and nested format
        raw_answers = getattr(input_data, "answers", None)
        if isinstance(raw_answers, dict):
            answers = raw_answers
        else:
            answers = {}
        
        raw_annotations = getattr(input_data, "annotations", None)
        annotations = raw_annotations if isinstance(raw_annotations, dict) else None

        if not answers:
            # Need to collect answers from user
            # In a full implementation, this would integrate with TUI/CLI
            # For now, we'll return a message indicating user interaction is needed
            return await self._collect_user_answers(validated_input.questions)
        
        # Return the result with answers
        return ToolOutput(
            success=True,
            result={
                "questions": [q.model_dump() for q in validated_input.questions],
                "answers": answers,
                "annotations": annotations
            }
        )

    async def _collect_user_answers(self, questions: list[QuestionSchema]) -> ToolOutput:
        """
        Collect answers from user.
        
        This is a placeholder that returns a response indicating the tool
        needs user interaction. In the full TUI integration, this would
        display the question widget and wait for user input.
        """
        # For now, return a response that indicates user interaction is needed
        # The TUI handler will intercept this and display the question widget
        return ToolOutput(
            success=True,
            result={
                "questions": [q.model_dump() for q in questions],
                "answers": {},
                "annotations": None,
                "_requires_interaction": True
            },
            metadata={
                "requires_user_interaction": True,
                "tool_name": self.name
            }
        )

    def resolve_permission(self, args: dict) -> PermissionContext | None:
        """
        AskUserQuestionTool always requires user interaction.
        
        Returns a permission context requesting approval to ask questions.
        """
        return PermissionContext(
            permission=ToolPermission.ASK,
            reason="User needs to answer questions"
        )

    def get_function_definition(self) -> dict[str, Any]:
        """Get the tool definition in OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


# ============== Helper Functions ==============

def validate_html_preview(preview: str | None) -> str | None:
    """
    Validate HTML preview content.
    
    Returns an error message if the preview is invalid, or None if valid.
    """
    if preview is None:
        return None
    
    # Check for full document indicators
    import re
    if re.search(r'<\s*(html|body|!doctype)\b', preview, re.IGNORECASE):
        return 'preview must be an HTML fragment, not a full document (no <html>, <body>, or <!DOCTYPE>)'
    
    # Check for script/style tags
    if re.search(r'<\s*(script|style)\b', preview, re.IGNORECASE):
        return 'preview must not contain <script> or <style> tags. Use inline style attributes instead.'
    
    # Check that it contains HTML tags
    if not re.search(r'<\s*[a-z][^>]*>', preview, re.IGNORECASE):
        return 'preview must contain HTML. Wrap content in a tag like <div> or <pre>.'
    
    return None


def build_question_response(
    questions: list[QuestionSchema],
    answers: dict[str, str],
    annotations: dict[str, AnnotationSchema] | None = None
) -> str:
    """Build a human-readable response string from question answers."""
    parts = []
    for question in questions:
        answer = answers.get(question.question, "No answer")
        parts.append(f'"{question.question}" = "{answer}"')
    
    response = "User has answered your questions: " + ", ".join(parts)
    response += ". You can now continue with the user's answers in mind."
    
    return response