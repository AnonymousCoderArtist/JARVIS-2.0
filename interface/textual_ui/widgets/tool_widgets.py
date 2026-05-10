from __future__ import annotations

from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from interface.textual_ui.ansi_markdown import AnsiMarkdown as Markdown
from interface.textual_ui.cli_adapters import (
    AskUserQuestionResult,
    BashArgs,
    EditArgs,
    GrepArgs,
    LSArgs,
    ReadFileArgs,
    TodoArgs,
    WriteFileArgs,
)
from interface.textual_ui.tool_results import (
    BashResult,
    EditResult,
    GrepResult,
    LSResult,
    ReadFileResult,
    TodoResult,
    WriteFileResult,
)
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic


def _truncate_lines(content: str, max_lines: int) -> tuple[str, str | None]:
    """Truncate content to max_lines, returning (content, truncation_info)."""
    lines = content.strip("\n").split("\n")
    if len(lines) <= max_lines:
        return "\n".join(lines), None
    remaining = len(lines) - max_lines
    return "\n".join(lines[:max_lines]), f"… ({remaining} more lines)"


TArgs = TypeVar("TArgs", bound=BaseModel)
TResult = TypeVar("TResult", bound=BaseModel)


class ToolApprovalWidget(Generic[TArgs], Vertical):
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



class ToolResultWidget(Generic[TResult], Static, can_focus=True):
    """Base class for result widgets with typed result."""

    collapsed = reactive(True)

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
        self.warnings = warnings or []
        self.collapsed = collapsed
        self.add_class("tool-result-widget")

    def watch_collapsed(self, collapsed: bool) -> None:
        """Re-compose the widget when collapsed state changes."""
        # refresh() only repaints; we need re-compose to show/hide diff content
        self._recompose_on_collapse_change()

    def _recompose_on_collapse_change(self) -> None:
        """Re-compose and notify parent ToolResultMessage of collapsed change."""
        try:
            # Use Textual's recompose to rebuild children with new collapsed state
            self.recompose()
        except Exception:
            # Fallback to refresh if recompose fails
            self.refresh()
        # Notify parent ToolResultMessage about the toggle
        self._notify_parent_toggle()

    def _notify_parent_toggle(self) -> None:
        """Notify the parent ToolResultMessage about collapsed state change."""
        from interface.textual_ui.widgets.tools import ToolResultMessage
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ToolResultMessage):
                parent.collapsed = self.collapsed
                break
            parent = parent.parent

    def _footer(self, extra: str | None = None) -> ComposeResult:
        """Yield the footer with optional extra info."""
        if extra:
            yield NoMarkupStatic(extra, classes="tool-result-hint")

    def compose(self) -> ComposeResult:
        """Default: show result fields."""
        summary_text = f"└─ {self.message or 'result'}"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed and self.result:
            yielded = False
            # Handle both BaseModel and plain dict results
            if isinstance(self.result, BaseModel):
                field_names = type(self.result).model_fields or {}
                for field_name in field_names:
                    value = getattr(self.result, field_name)
                    if value is not None and value not in ("", []):
                        yield NoMarkupStatic(
                            f"{field_name}: {value}", classes="tool-result-detail"
                        )
                        yielded = True
            elif isinstance(self.result, dict):
                for field_name, value in self.result.items():
                    if value is not None and value not in ("", []):
                        yield NoMarkupStatic(
                            f"{field_name}: {value}", classes="tool-result-detail"
                        )
                        yielded = True
            
            if not yielded:
                yield NoMarkupStatic(str(self.result), classes="tool-result-detail")
                
        yield from self._footer()

    def on_click(self, event) -> None:
        """Toggle collapsed/expanded state on click."""
        # Toggle if we have content
        if self.result and (
            (hasattr(self.result, 'matches') and self.result.matches) or
            (hasattr(self.result, 'items') and self.result.items) or
            (hasattr(self.result, '__dict__') and any(getattr(self.result, attr, None) not in ("", [], None) for attr in dir(self.result) if not attr.startswith('_'))) or
            (isinstance(self.result, dict) and any(v not in ("", [], None) for v in self.result.values()))
        ):
            self.collapsed = not self.collapsed


class BashApprovalWidget(ToolApprovalWidget[BashArgs]):
    def compose(self) -> ComposeResult:
        command = self.args.command if isinstance(self.args, BaseModel) else self.args.get("command", "")
        yield Markdown(f"```bash\n{command}\n```")


class BashResultWidget(ToolResultWidget[BashResult]):
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return

        # Result summary
        summary_text = f"└─ exit code {self.result.returncode}"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed:
            if self.result.stdout:
                content, truncation_info = _truncate_lines(self.result.stdout, 15)
                yield Markdown(f"```text\n{content}\n```")
                if truncation_info:
                    yield NoMarkupStatic(truncation_info, classes="tool-result-hint")

            if self.result.stderr:
                yield NoMarkupStatic(self.result.stderr, classes="tool-result-error")

            yield from self._footer()
        else:
            yield from self._footer()

class EditApprovalWidget(ToolApprovalWidget[Any]):
    def compose(self) -> ComposeResult:
        replacements = self.args.replacements if isinstance(self.args, BaseModel) else self.args.get("replacements", [])
        
        if not replacements:
            yield NoMarkupStatic("No replacements specified", classes="approval-description")
            return

        # Group replacements by file path
        from collections import defaultdict
        files_to_edits = defaultdict(list)
        for edit in replacements:
            file_path = edit.get("filePath") or edit.get("file_path", "unknown")
            files_to_edits[file_path].append(edit)

        for file_path, edits in files_to_edits.items():
            yield NoMarkupStatic(f"File: {file_path}", classes="approval-description")
            yield NoMarkupStatic("")

            path = Path(file_path)
            try:
                if path.exists():
                    old_content = path.read_text(encoding="utf-8")
                    
                    new_content = old_content
                    for edit in edits:
                        old_str = edit.get("oldString") or edit.get("old_string", "")
                        new_str = edit.get("newString") or edit.get("new_string", "")
                        if old_str:
                            new_content = new_content.replace(old_str, new_str)

                    import difflib
                    diff = difflib.unified_diff(
                        old_content.splitlines(),
                        new_content.splitlines(),
                        lineterm="",
                    )
                    diff_text = "\n".join(diff)
                    if diff_text:
                        diff_lines = parse_diff_text(diff_text)
                        from interface.textual_ui.widgets.tools import DiffBlock
                        yield DiffBlock(diff_lines, context_lines=3)
                    else:
                        yield NoMarkupStatic("No changes (content is identical after replacement)", classes="tool-result-muted")
                else:
                    yield NoMarkupStatic("File does not exist (cannot show diff)", classes="tool-result-error")
                    for edit in edits:
                        old_str = edit.get("oldString") or edit.get("old_string", "")
                        new_str = edit.get("newString") or edit.get("new_string", "")
                        yield Markdown(f"Replace:\n```\n{old_str}\n```\nWith:\n```\n{new_str}\n```")
            except Exception as e:
                yield NoMarkupStatic(f"Error reading file for diff: {e}", classes="tool-result-error")
                for edit in edits:
                    old_str = edit.get("oldString") or edit.get("old_string", "")
                    new_str = edit.get("newString") or edit.get("new_string", "")
                    yield Markdown(f"Replace:\n```\n{old_str}\n```\nWith:\n```\n{new_str}\n```")


class WriteFileApprovalWidget(ToolApprovalWidget[WriteFileArgs]):
    def compose(self) -> ComposeResult:
        file_path = self.args.file_path if isinstance(self.args, BaseModel) else self.args.get("file_path", self.args.get("filePath", ""))
        path = Path(file_path)
        content = self.args.content if isinstance(self.args, BaseModel) else self.args.get("content", "")

        yield NoMarkupStatic(f"File: {file_path}", classes="approval-description")
        yield NoMarkupStatic("")

        try:
            if path.exists():
                old_content = path.read_text(encoding="utf-8")
                import difflib
                diff = difflib.unified_diff(
                    old_content.splitlines(),
                    content.splitlines(),
                    lineterm="",
                )
                diff_text = "\n".join(diff)
                if diff_text:
                    diff_lines = parse_diff_text(diff_text)
                    from interface.textual_ui.widgets.tools import DiffBlock
                    yield DiffBlock(diff_lines, context_lines=3)
                else:
                    yield NoMarkupStatic("No changes (content is identical)", classes="tool-result-muted")
            else:
                # New file
                yield NoMarkupStatic("New file", classes="tool-result-summary")
                file_extension = path.suffix.lstrip(".") or "text"
                yield Markdown(f"```{file_extension}\n{content}\n```")
        except Exception as e:
            yield NoMarkupStatic(f"Error reading file for diff: {e}", classes="tool-result-error")
            # Fallback to showing content
            file_extension = path.suffix.lstrip(".") or "text"
            yield Markdown(f"```{file_extension}\n{content}\n```")


class WriteFileResultWidget(ToolResultWidget[WriteFileResult]):
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return

        # Check if it's an edit operation (replacements > 0) or a write operation
        if self.result.replacements > 0:
            # Edit operation
            summary_text = f"└─ {self.result.replacements} replacement(s)"
            if self.collapsed:
                summary_text += " • Ctrl+O to expand"
            yield NoMarkupStatic(summary_text, classes="tool-result-summary")

            if not self.collapsed:
                # Show diff if available
                if self.result.diff:
                    diff_lines = parse_diff_text(self.result.diff)
                    if diff_lines:
                        # Lazy import DiffBlock
                        from interface.textual_ui.widgets.tools import DiffBlock
                        yield DiffBlock(diff_lines, context_lines=3)
                # Show new content
                ext = Path(self.result.path).suffix.lstrip(".") or "text"
                content, truncation_info = _truncate_lines(self.result.content, 15)
                yield Markdown(f"```{ext}\n{content}\n```")
                yield from self._footer(truncation_info)
            else:
                yield from self._footer()
        else:
            # Write operation
            summary_text = f"└─ {self.result.bytes_written} bytes written"
            if self.collapsed:
                summary_text += " • Ctrl+O to expand"
            yield NoMarkupStatic(summary_text, classes="tool-result-summary")

            if not self.collapsed:
                # Show diff if available
                if self.result.diff:
                    diff_lines = parse_diff_text(self.result.diff)
                    if diff_lines:
                        # Lazy import DiffBlock
                        from interface.textual_ui.widgets.tools import DiffBlock
                        yield DiffBlock(diff_lines, context_lines=3)
                # Show content
                ext = Path(self.result.path).suffix.lstrip(".") or "text"
                content, truncation_info = _truncate_lines(self.result.content, 15)
                yield Markdown(f"```{ext}\n{content}\n```")
                yield from self._footer(truncation_info)
            else:
                yield from self._footer()


class EditResultWidget(ToolResultWidget[EditResult]):
    """Result widget for the edit tool - shows diff for file modifications."""
    
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return

        # Get file path - handle both 'file' and 'file_path' keys
        file_path = self.result.file_path or self.result.file or "unknown"
        occurrences = self.result.occurrences_replaced or 0
        
        # Summary line
        summary_text = f"└─ {occurrences} replacement(s) in {file_path}"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed:
            # Show diff if available
            diff_text = self.result.diff or self.result.unified_diff or ""
            if diff_text:
                diff_lines = parse_diff_text(diff_text)
                if diff_lines:
                    from interface.textual_ui.widgets.tools import DiffBlock
                    yield DiffBlock(diff_lines, context_lines=3)
            
            # Show status
            status = self.result.status or "success"
            status_class = "tool-result-success" if status == "success" else "tool-result-error"
            yield NoMarkupStatic(f"   Status: {status}", classes=status_class)
            
            yield from self._footer()
        else:
            yield from self._footer()


def parse_diff_text(diff_text: str) -> list:
    """Parse unified diff text into DiffLine objects."""
    from interface.textual_ui.widgets.tools import DiffLine
    
    lines = []
    old_line_num = None
    new_line_num = None
    
    for line in diff_text.split('\n'):
        if line.startswith('@@'):
            # Parse hunk header to get line numbers
            # Format: @@ -old_start,old_count +new_start,new_count @@
            parts = line.split(' ')
            if len(parts) >= 3:
                old_part = parts[1]
                new_part = parts[2]
                if old_part.startswith('-'):
                    try:
                        old_line_num = int(old_part.split(',')[0][1:])
                    except (ValueError, IndexError):
                        old_line_num = None
                if new_part.startswith('+'):
                    try:
                        new_line_num = int(new_part.split(',')[0][1:])
                    except (ValueError, IndexError):
                        new_line_num = None
            lines.append(DiffLine(line_number=None, content=line, prefix=" "))
        elif line.startswith('+++') or line.startswith('---') or line.startswith('diff '):
            # Skip file header lines
            lines.append(DiffLine(line_number=None, content=line, prefix=" "))
        elif line.startswith('+'):
            lines.append(DiffLine(line_number=new_line_num, content=line[1:], prefix="+"))
            if new_line_num is not None:
                new_line_num += 1
        elif line.startswith('-'):
            lines.append(DiffLine(line_number=old_line_num, content=line[1:], prefix="-"))
            if old_line_num is not None:
                old_line_num += 1
        elif line.startswith(' '):
            lines.append(DiffLine(line_number=new_line_num, content=line[1:], prefix=" "))
            if old_line_num is not None:
                old_line_num += 1
            if new_line_num is not None:
                new_line_num += 1
        elif line:
            # Any other line
            lines.append(DiffLine(line_number=None, content=line, prefix=" "))
    
    return lines


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
            yield NoMarkupStatic("└─ no todos", classes="tool-result-muted")
            yield from self._footer()
            return

        total_todos = len(self.result.todos)
        summary_text = f"└─ {total_todos} items"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed:
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
                    yield NoMarkupStatic(f"   {icon} {todo.content}", classes=f"todo-{status}")
            yield from self._footer()
        else:
            yield from self._footer()

    def _get_status_icon(self, status: str) -> str:
        icons = {
            "pending": "[ ]",
            "in_progress": "[~]",
            "completed": "[x]",
            "cancelled": "[-]",
        }
        return icons.get(status, "[ ]")


class ReadFileApprovalWidget(ToolApprovalWidget[ReadFileArgs]):
    def compose(self) -> ComposeResult:
        files = self.args.files if isinstance(self.args, BaseModel) else self.args.get("files", [])
        encoding = self.args.encoding if isinstance(self.args, BaseModel) else self.args.get("encoding", "utf-8")
        yield NoMarkupStatic(f"files: {len(files)} file(s)", classes="approval-description approval-read-file-count")
        yield NoMarkupStatic(f"encoding: {encoding}", classes="approval-description")


class ReadFileResultWidget(ToolResultWidget[ReadFileResult]):
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return

        # Result summary
        lines = self.result.content.split("\n")
        line_count = len(lines)
        summary_text = f"└─ {line_count} lines loaded"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary tool-result-read-summary")

        if not self.collapsed:
            for warning in self.warnings:
                yield NoMarkupStatic(f"warning: {warning}", classes="tool-result-warning tool-result-read-warning")

            # Show content
            ext = Path(self.result.path).suffix.lstrip(".") or "text"
            content, truncation_info = _truncate_lines(self.result.content, 15)
            yield Markdown(f"```{ext}\n{content}\n```")
            yield from self._footer(truncation_info)
        else:
            yield from self._footer()


class GrepApprovalWidget(ToolApprovalWidget[GrepArgs]):
    """Grep approval widget with clean visual hierarchy.

    Features:
    - Tool identification (text only)
    - Query type indicator (regexp vs literal)
    - Optional parameters (path, max_matches, include_pattern)
    """

    def compose(self) -> ComposeResult:
        query = self.args.query if isinstance(self.args, BaseModel) else self.args.get("query", "")
        path = self.args.path if isinstance(self.args, BaseModel) else self.args.get("path", ".")
        is_regexp = self.args.is_regexp if isinstance(self.args, BaseModel) else self.args.get("is_regexp", False)
        max_matches = self.args.max_matches if isinstance(self.args, BaseModel) else self.args.get("max_matches", None)
        include_pattern = self.args.include_pattern if isinstance(self.args, BaseModel) else self.args.get("include_pattern", None)

        # Tool header with type indicator
        query_type = "regexp" if is_regexp else "literal"
        yield NoMarkupStatic(f"grep [{query_type}]", classes="approval-tool-name")
        yield Static("")  # Spacer

        # Main pattern highlighted
        yield NoMarkupStatic(f'"{query}"', classes="approval-grep-query")

        # Optional parameters with subtle styling
        if path != ".":
            yield NoMarkupStatic(f"  path: {path}", classes="approval-grep-param")
        if max_matches:
            yield NoMarkupStatic(f"  max: {max_matches}", classes="approval-grep-param")
        if include_pattern:
            yield NoMarkupStatic(f"  filter: {include_pattern}", classes="approval-grep-param")


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

        matches = self.result.matches
        total_matches = len(matches)

        # Branch with match count
        summary_text = f"└─ {total_matches} matches"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed:
            # Show matches with line numbers and file paths
            max_matches_to_show = 15
            for match in matches[:max_matches_to_show]:
                file = match.file
                line_num = match.line
                content = match.content

                # Truncate very long content
                display_content = content[:100] + "…" if len(content) > 100 else content
                # Use markup for colors: bright black for path, yellow for line
                yield Static(f"   [ansi_bright_black]{file}[/][ansi_bright_black]:[/][ansi_bright_yellow]{line_num}[/][ansi_bright_black]:[/] {display_content}", classes="tool-result-match")

            if total_matches > max_matches_to_show:
                remaining = total_matches - max_matches_to_show
                yield NoMarkupStatic(f"   ... ({remaining} more lines • Ctrl+O to expand)", classes="tool-result-hint")

        yield from self._footer()



class LSResultWidget(ToolResultWidget[LSResult]):
    """LS result widget.

    Layout:
    └─ 24 entries
       .env
       src/
    """

    def compose(self) -> ComposeResult:
        if not self.result or not self.result.items:
            yield NoMarkupStatic("└─ empty directory", classes="tool-result-muted")
            yield from self._footer()
            return

        items = self.result.items
        total_items = len(items)

        # Branch with count
        summary_text = f"└─ {total_items} entries"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed:
            max_items_to_show = 15
            for item in items[:max_items_to_show]:
                is_dir = item.endswith("/")
                item_class = "tool-result-ls-dir" if is_dir else "tool-result-ls-file"
                yield Static(f"   {item}", classes=f"tool-result-ls-item {item_class}")

            if total_items > max_items_to_show:
                remaining = total_items - max_items_to_show
                yield NoMarkupStatic(f"   ... {remaining} more entries", classes="tool-result-ls-hint")

        yield from self._footer()


class AskUserQuestionResultWidget(ToolResultWidget[AskUserQuestionResult]):
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.answers:
            yield NoMarkupStatic("└─ cancelled", classes="tool-result-muted")
            yield from self._footer()
            return

        summary_text = f"└─ {len(self.result.answers)} answers"
        if self.collapsed:
            summary_text += " • Ctrl+O to expand"
        yield NoMarkupStatic(summary_text, classes="tool-result-summary")

        if not self.collapsed:
            for answer in self.result.answers:
                if len(self.result.answers) > 1:
                    yield NoMarkupStatic(f"   Q: {answer.question}", classes="tool-result-detail")
                prefix = "(Other) " if answer.is_other else ""
                yield NoMarkupStatic(f"   A: {prefix}{answer.answer}", classes="ask-user-answer")
            yield from self._footer()
        else:
            yield from self._footer()


APPROVAL_WIDGETS: dict[str, type[ToolApprovalWidget]] = {
    "bash": BashApprovalWidget,
    "read": ReadFileApprovalWidget,
    "read_file": ReadFileApprovalWidget,
    "write": WriteFileApprovalWidget,
    "write_file": WriteFileApprovalWidget,
    "grep": GrepApprovalWidget,
    "todo": TodoApprovalWidget,
    "edit": EditApprovalWidget,
    "str_replace_editor": EditApprovalWidget,
}

RESULT_WIDGETS: dict[str, type[ToolResultWidget]] = {
    "bash": BashResultWidget,
    "read": ReadFileResultWidget,
    "read_file": ReadFileResultWidget,
    "write": WriteFileResultWidget,
    "write_file": WriteFileResultWidget,
    "edit": EditResultWidget,  # Use EditResultWidget for edit (shows diff)
    "grep": GrepResultWidget,
    "ls": LSResultWidget,
    "todo": TodoResultWidget,
    "ask_user_question": AskUserQuestionResultWidget,
}

ARGS_MODELS: dict[str, type[BaseModel]] = {
    "bash": BashArgs,
    "read": ReadFileArgs,
    "read_file": ReadFileArgs,
    "write": WriteFileArgs,
    "write_file": WriteFileArgs,
    "edit": EditArgs,
    "grep": GrepArgs,
    "ls": LSArgs,
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
    result: Any | None,
    success: bool,
    message: str,
    collapsed: bool = True,
    warnings: list[str] | None = None,
) -> ToolResultWidget:
    widget_class = RESULT_WIDGETS.get(tool_name, ToolResultWidget)

    # Wrap results into appropriate models if they come as raw data
    if tool_name == "ls" and isinstance(result, list):
        result = LSResult(items=result)
    elif tool_name == "grep" and isinstance(result, list):
        from interface.textual_ui.tool_results import GrepMatch
        matches = []
        for r in result:
            if isinstance(r, dict):
                matches.append(GrepMatch(
                    file=r.get("file", "unknown"),
                    line=r.get("line", 0),
                    content=r.get("content", "")
                ))
        result = GrepResult(matches=matches)
    elif tool_name == "edit" and isinstance(result, dict):
        # Convert edit tool result dict to EditResult model
        result = EditResult(
            file=result.get("file", result.get("file_path", "")),
            file_path=result.get("file_path", result.get("file", "")),
            status=result.get("status", "success"),
            occurrences_replaced=result.get("occurrences_replaced", result.get("replacements", 0)),
            diff=result.get("diff", result.get("unified_diff", "")),
            unified_diff=result.get("unified_diff", result.get("diff", "")),
        )

    return widget_class(result, success, message, collapsed, warnings)
