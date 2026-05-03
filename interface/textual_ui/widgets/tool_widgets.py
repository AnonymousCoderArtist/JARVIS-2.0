from __future__ import annotations

import difflib
from pathlib import Path

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from interface.textual_ui.ansi_markdown import AnsiMarkdown as Markdown
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.cli_adapters import (
    AskUserQuestionResult,
    BashArgs,
    GrepArgs,
    ReadFileArgs,
    TodoArgs,
    WriteFileArgs,
)
from interface.textual_ui.tool_results import (
    BashResult,
    GrepResult,
    ReadFileResult,
    TodoResult,
    WriteFileResult,
)


def _truncate_lines(content: str, max_lines: int) -> tuple[str, str | None]:
    """Truncate content to max_lines, returning (content, truncation_info)."""
    lines = content.strip("\n").split("\n")
    if len(lines) <= max_lines:
        return "\n".join(lines), None
    remaining = len(lines) - max_lines
    return "\n".join(lines[:max_lines]), f"… ({remaining} more lines)"


class ToolApprovalWidget[TArgs: BaseModel](Vertical):
    """Base class for approval widgets with typed args."""

    def __init__(self, args: TArgs) -> None:
        super().__init__()
        self.args = args
        self.add_class("tool-approval-widget")

    def compose(self) -> ComposeResult:
        MAX_MSG_SIZE = 150
        model_cls = type(self.args)
        
        # Handle both BaseModel and plain dict args
        if isinstance(self.args, BaseModel):
            field_names = model_cls.model_fields or {}
        elif isinstance(self.args, dict):
            field_names = self.args.keys()
        else:
            field_names = {}
        
        for field_name in field_names:
            value = getattr(self.args, field_name, None) if not isinstance(self.args, dict) else self.args.get(field_name)
            if value is None or value in ("", []):
                continue
            value_str = str(value)
            if len(value_str) > MAX_MSG_SIZE:
                hidden = len(value_str) - MAX_MSG_SIZE
                value_str = value_str[:MAX_MSG_SIZE] + f"… ({hidden} more characters)"
            yield NoMarkupStatic(
                f"{field_name}: {value_str}", classes="approval-description"
            )


class ToolResultWidget[TResult: BaseModel](Static, can_focus=True):
    """Base class for result widgets with typed result."""

    def __init__(
        self,
        result: TResult | None,
        success: bool,
        message: str,
        collapsed: bool = True,
        warnings: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.result = result
        self.success = success
        self.message = message
        self.collapsed = collapsed
        self.warnings = warnings or []
        self.add_class("tool-result-widget")

    def _footer(self, extra: str | None = None) -> ComposeResult:
        """Yield the footer with optional extra info."""
        if extra:
            yield NoMarkupStatic(extra, classes="tool-result-hint")

    def compose(self) -> ComposeResult:
        """Default: show result fields."""
        if not self.collapsed and self.result:
            # Handle both BaseModel and plain dict results
            if isinstance(self.result, BaseModel):
                field_names = type(self.result).model_fields or {}
                for field_name in field_names:
                    value = getattr(self.result, field_name)
                    if value is not None and value not in ("", []):
                        yield NoMarkupStatic(
                            f"{field_name}: {value}", classes="tool-result-detail"
                        )
            elif isinstance(self.result, dict):
                for field_name, value in self.result.items():
                    if value is not None and value not in ("", []):
                        yield NoMarkupStatic(
                            f"{field_name}: {value}", classes="tool-result-detail"
                        )
        yield from self._footer()

    def on_click(self, event) -> None:
        """Toggle collapsed/expanded state on click."""
        if not self.collapsed:
            # Only allow collapsing if we have content to show
            if self.result and (
                (hasattr(self.result, 'matches') and self.result.matches) or
                (hasattr(self.result, '__dict__') and any(getattr(self.result, attr, None) not in ("", [], None) for attr in dir(self.result) if not attr.startswith('_'))) or
                (isinstance(self.result, dict) and any(v not in ("", [], None) for v in self.result.values()))
            ):
                self.collapsed = True
                self.refresh()
        else:
            # Expand if we have content
            if self.result and (
                (hasattr(self.result, 'matches') and self.result.matches) or
                (hasattr(self.result, '__dict__') and any(getattr(self.result, attr, None) not in ("", [], None) for attr in dir(self.result) if not attr.startswith('_'))) or
                (isinstance(self.result, dict) and any(v not in ("", [], None) for v in self.result.values()))
            ):
                self.collapsed = False
                self.refresh()


class BashApprovalWidget(ToolApprovalWidget[BashArgs]):
    def compose(self) -> ComposeResult:
        command = self.args.command if isinstance(self.args, BaseModel) else self.args.get("command", "")
        yield Markdown(f"```bash\n{command}\n```")


class BashResultWidget(ToolResultWidget[BashResult]):
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return
        if self.collapsed:
            truncation_info = None
            if self.result.stdout:
                content, truncation_info = _truncate_lines(self.result.stdout, 10)
                yield NoMarkupStatic(content, classes="tool-result-detail")
            else:
                yield NoMarkupStatic("(no content)", classes="tool-result-detail")
            yield from self._footer(truncation_info)
            return
        yield NoMarkupStatic(
            f"returncode: {self.result.returncode}", classes="tool-result-detail"
        )
        if self.result.stdout:
            sep = "\n" if "\n" in self.result.stdout else " "
            yield NoMarkupStatic(
                f"stdout:{sep}{self.result.stdout}", classes="tool-result-detail"
            )
        if self.result.stderr:
            sep = "\n" if "\n" in self.result.stderr else " "
            yield NoMarkupStatic(
                f"stderr:{sep}{self.result.stderr}", classes="tool-result-detail"
            )
        yield from self._footer()


class WriteFileApprovalWidget(ToolApprovalWidget[WriteFileArgs]):
    def compose(self) -> ComposeResult:
        file_path = self.args.filePath if isinstance(self.args, BaseModel) else self.args.get("filePath", "")
        path = Path(file_path)
        file_extension = path.suffix.lstrip(".") or "text"
        content = self.args.content if isinstance(self.args, BaseModel) else self.args.get("content", "")

        yield NoMarkupStatic(f"File: {file_path}", classes="approval-description")
        yield NoMarkupStatic("")
        yield Markdown(f"```{file_extension}\n{content}\n```")


class WriteFileResultWidget(ToolResultWidget[WriteFileResult]):
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return
        ext = Path(self.result.path).suffix.lstrip(".") or "text"
        if self.collapsed:
            truncation_info = None
            if self.result.content:
                content, truncation_info = _truncate_lines(self.result.content, 10)
                yield Markdown(f"```{ext}\n{content}\n```")
            yield from self._footer(truncation_info)
            return
        yield NoMarkupStatic(f"Path: {self.result.path}", classes="tool-result-detail")
        yield NoMarkupStatic(
            f"Bytes: {self.result.bytes_written}", classes="tool-result-detail"
        )
        if self.result.content:
            yield NoMarkupStatic("")
            content, _ = _truncate_lines(self.result.content, 10)
            yield Markdown(f"```{ext}\n{content}\n```")
        yield from self._footer()


class TodoApprovalWidget(ToolApprovalWidget[TodoArgs]):
    def compose(self) -> ComposeResult:
        action = self.args.action if isinstance(self.args, BaseModel) else self.args.get("action", "")
        yield NoMarkupStatic(
            f"Action: {action}", classes="approval-description"
        )
        todos = self.args.todos if isinstance(self.args, BaseModel) else self.args.get("todos", [])
        if todos:
            yield NoMarkupStatic(
                f"Todos: {len(todos)} items", classes="approval-description"
            )


class TodoResultWidget(ToolResultWidget[TodoResult]):
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.todos:
            yield NoMarkupStatic("No todos", classes="todo-empty")
            yield from self._footer()
            return

        by_status: dict[str, list] = {
            "in_progress": [],
            "pending": [],
            "completed": [],
            "cancelled": [],
        }
        for todo in self.result.todos:
            status = (
                todo.status.value if hasattr(todo.status, "value") else str(todo.status)
            )
            if status in by_status:
                by_status[status].append(todo)

        for status in ["in_progress", "pending", "completed", "cancelled"]:
            for todo in by_status[status]:
                icon = self._get_status_icon(status)
                yield NoMarkupStatic(f"{icon} {todo.content}", classes=f"todo-{status}")
        yield from self._footer()

    def _get_status_icon(self, status: str) -> str:
        icons = {"pending": "☐", "in_progress": "☐", "completed": "☑", "cancelled": "☒"}
        return icons.get(status, "☐")


class ReadFileApprovalWidget(ToolApprovalWidget[ReadFileArgs]):
    def compose(self) -> ComposeResult:
        files = self.args.files if isinstance(self.args, BaseModel) else self.args.get("files", [])
        encoding = self.args.encoding if isinstance(self.args, BaseModel) else self.args.get("encoding", "utf-8")
        yield NoMarkupStatic(f"files: {len(files)} file(s)", classes="approval-description")
        yield NoMarkupStatic(f"encoding: {encoding}", classes="approval-description")


class ReadFileResultWidget(ToolResultWidget[ReadFileResult]):
    def compose(self) -> ComposeResult:
        if self.collapsed:
            yield from self._footer()
            return
        if self.result:
            yield NoMarkupStatic(
                f"Path: {self.result.path}", classes="tool-result-detail"
            )
        for warning in self.warnings:
            yield NoMarkupStatic(f"⚠ {warning}", classes="tool-result-warning")
        truncation_info = None
        if self.result and self.result.content:
            yield NoMarkupStatic("")
            ext = Path(self.result.path).suffix.lstrip(".") or "text"
            content, truncation_info = _truncate_lines(self.result.content, 10)
            yield Markdown(f"```{ext}\n{content}\n```")
        yield from self._footer(truncation_info)


class GrepApprovalWidget(ToolApprovalWidget[GrepArgs]):
    """Modern grep approval widget with clean visual hierarchy.
    
    Features:
    - Clear tool identification with icon
    - Query type indicator (regexp vs literal)
    - Optional parameters (path, max_matches, include_pattern)
    - Clean spacing and iconography
    """
    
    def compose(self) -> ComposeResult:
        query = self.args.query if isinstance(self.args, BaseModel) else self.args.get("query", "")
        path = self.args.path if isinstance(self.args, BaseModel) else self.args.get("path", ".")
        is_regexp = self.args.is_regexp if isinstance(self.args, BaseModel) else self.args.get("is_regexp", False)
        max_matches = self.args.max_matches if isinstance(self.args, BaseModel) else self.args.get("max_matches", None)
        include_pattern = self.args.include_pattern if isinstance(self.args, BaseModel) else self.args.get("include_pattern", None)
        
        # Tool header with icon and type indicator
        query_type = "regexp" if is_regexp else "literal"
        yield NoMarkupStatic(f"🔍 grep [{query_type}]", classes="approval-tool-name")
        yield Static("")  # Spacer
        
        # Main pattern highlighted
        yield NoMarkupStatic(f'"{query}"', classes="approval-grep-query")
        
        # Optional parameters with subtle styling
        if path != ".":
            yield NoMarkupStatic(f"  ↳ path: {path}", classes="approval-grep-param")
        if max_matches:
            yield NoMarkupStatic(f"  ↳ max: {max_matches}", classes="approval-grep-param")
        if include_pattern:
            yield NoMarkupStatic(f"  ↳ filter: {include_pattern}", classes="approval-grep-param")


class GrepResultWidget(ToolResultWidget[GrepResult]):
    """Modern grep result widget matching design.
    
    Layout:
    └─ 24 matches
       src/file.py:10: content
    """
    
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.matches:
            yield NoMarkupStatic("└─ no matches", classes="tool-result-muted")
            yield from self._footer()
            return
        
        matches_text = self.result.matches
        lines = [l for l in matches_text.split("\n") if l.strip()]
        total_matches = len(lines)
        
        # Branch with match count
        summary_text = f"└─ {total_matches} matches"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")
        
        if not self.collapsed:
            # Show matches with line numbers and file paths
            max_matches_to_show = 15
            for line in lines[:max_matches_to_show]:
                # Split line to format it: file:line:content
                parts = line.split(":", 2)
                if len(parts) == 3:
                    file, line_num, content = parts
                    # Truncate very long content
                    display_content = content[:100] + "…" if len(content) > 100 else content
                    # Use markup for colors: bright black for path, yellow for line
                    yield Static(f"   [ansi_bright_black]{file}[/][ansi_bright_black]:[/][ansi_bright_yellow]{line_num}[/][ansi_bright_black]:[/] {display_content}", classes="tool-result-match")
                else:
                    display_line = line[:120] + "…" if len(line) > 120 else line
                    yield NoMarkupStatic(f"   {display_line}", classes="tool-result-match")
            
            if total_matches > max_matches_to_show:
                remaining = total_matches - max_matches_to_show
                yield NoMarkupStatic(f"   ... ({remaining} more lines • Ctrl+O to expand)", classes="tool-result-hint")
        
        yield from self._footer()



class AskUserQuestionResultWidget(ToolResultWidget[AskUserQuestionResult]):
    def compose(self) -> ComposeResult:
        if self.collapsed or not self.result:
            yield from self._footer()
            return

        for answer in self.result.answers:
            if len(self.result.answers) > 1:
                yield NoMarkupStatic(answer.question, classes="tool-result-detail")
            prefix = "(Other) " if answer.is_other else ""
            yield NoMarkupStatic(f"{prefix}{answer.answer}", classes="ask-user-answer")
        yield from self._footer()


APPROVAL_WIDGETS: dict[str, type[ToolApprovalWidget]] = {
    "bash": BashApprovalWidget,
    "read_file": ReadFileApprovalWidget,
    "write_file": WriteFileApprovalWidget,
    "grep": GrepApprovalWidget,
    "todo": TodoApprovalWidget,
}

RESULT_WIDGETS: dict[str, type[ToolResultWidget]] = {
    "bash": BashResultWidget,
    "read_file": ReadFileResultWidget,
    "write_file": WriteFileResultWidget,
    "grep": GrepResultWidget,
    "todo": TodoResultWidget,
    "ask_user_question": AskUserQuestionResultWidget,
}

ARGS_MODELS: dict[str, type[BaseModel]] = {
    "bash": BashArgs,
    "read_file": ReadFileArgs,
    "write_file": WriteFileArgs,
    "grep": GrepArgs,
    "todo": TodoArgs,
}


def get_approval_widget(tool_name: str, args: BaseModel | dict) -> ToolApprovalWidget:
    widget_class = APPROVAL_WIDGETS.get(tool_name, ToolApprovalWidget)
    # Convert dict to appropriate BaseModel if needed
    if isinstance(args, dict):
        from pydantic import create_model
        args_model_cls = ARGS_MODELS.get(tool_name)
        if args_model_cls:
            args = args_model_cls(**args)
        else:
            # Fallback: wrap in generic container
            field_definitions = {k: (type(v), ...) for k, v in args.items()}
            GenericArgs = create_model("GenericArgs", **field_definitions)  # type: ignore
            args = GenericArgs(**args)
    return widget_class(args)


def get_result_widget(
    tool_name: str,
    result: BaseModel | None,
    success: bool,
    message: str,
    collapsed: bool = True,
    warnings: list[str] | None = None,
) -> ToolResultWidget:
    widget_class = RESULT_WIDGETS.get(tool_name, ToolResultWidget)
    return widget_class(result, success, message, collapsed, warnings)