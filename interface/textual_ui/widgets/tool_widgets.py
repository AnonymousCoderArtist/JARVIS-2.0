"""Modern tool widgets with expand/collapse functionality.

This module provides consistent UI widgets for various tools (bash, grep, ls, find, etc.)
with unified styling, expand/collapse logic, and color coding.

Design Pattern:
- Each tool has an ApprovalWidget and ResultWidget
- Result widgets support expand/collapse via Ctrl+O or click
- Collapsed state shows a summary line with branch indicator (└─)
- Expanded state shows detailed output
- Colors are consistent across all tools using ANSI color names
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static
from textual.reactive import reactive
from textual.message import Message

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.messages import NonSelectableStatic
from interface.textual_ui.cli_adapters import (
    AskUserQuestionResult,
    BashArgs,
    GrepArgs,
    LSArgs,
    FindArgs,
    ReadFileArgs,
    TodoArgs,
    WriteFileArgs,
)
from interface.textual_ui.tool_results import (
    BashResult,
    GrepResult,
    LSResult,
    FindResult,
    ReadFileResult,
    TodoResult,
    WriteFileResult,
)


def _truncate_lines(content: str, max_lines: int) -> tuple[str, int]:
    """Truncate content to max_lines, returning (content, remaining_count)."""
    lines = content.strip("\n").split("\n")
    if len(lines) <= max_lines:
        return "\n".join(lines), 0
    remaining = len(lines) - max_lines
    return "\n".join(lines[:max_lines]), remaining


def _get_relative_path(path_str: str, base: str = ".") -> str:
    """Get relative path from base directory for cleaner display."""
    try:
        p = Path(path_str).resolve()
        cwd = Path(base).resolve()
        if p == cwd:
            return "."
        if p.is_relative_to(cwd):
            rel = p.relative_to(cwd)
            return str(rel).replace("\\", "/") or "."
    except Exception:
        pass
    return path_str


# =============================================================================
# BASE CLASSES
# =============================================================================

class ToolApprovalWidget[TArgs: BaseModel](Vertical):
    """Base class for approval widgets with typed args."""

    def __init__(self, args: TArgs) -> None:
        super().__init__()
        self.args = args
        self.add_class("tool-approval-widget")

    def compose(self) -> ComposeResult:
        MAX_MSG_SIZE = 150
        model_cls = type(self.args)
        
        field_names = model_cls.model_fields or {}
        
        for field_name in field_names:
            value = getattr(self.args, field_name, None)
            if value is None or value in ("", []):
                continue
            value_str = str(value)
            if len(value_str) > MAX_MSG_SIZE:
                hidden = len(value_str) - MAX_MSG_SIZE
                value_str = value_str[:MAX_MSG_SIZE] + f"... ({hidden} more chars)"
            yield NoMarkupStatic(
                f"{field_name}: {value_str}", classes="approval-description"
            )


class ToolResultWidget[TResult: BaseModel](Static, can_focus=True):
    """Base class for result widgets with typed result and expand/collapse."""
    
    collapsed = reactive(True)

    class ToggleRequest(Message):
        """Request to toggle the parent's collapsed state."""
        def __init__(self, collapsed: bool) -> None:
            self.collapsed = collapsed
            super().__init__()

    BINDINGS = [
        Binding("ctrl+o", "toggle_expand", "Expand/Collapse", show=False),
    ]

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
        """Update the widget when collapsed state changes."""
        # Textual's reactive watchers handle async methods specially
        _ = self.recompose()

    def compose(self) -> ComposeResult:
        """Default: show result fields."""
        if not self.collapsed and self.result:
            if isinstance(self.result, BaseModel):
                field_names = type(self.result).model_fields or {}
                for field_name in field_names:
                    value = getattr(self.result, field_name)
                    if value is not None and value not in ("", []):
                        yield NoMarkupStatic(
                            f"{field_name}: {value}", classes="tool-result-detail"
                        )
        yield from self._footer()

    def _footer(self, extra: str | None = None) -> ComposeResult:
        """Yield the footer with optional extra info."""
        if extra:
            yield NoMarkupStatic(extra, classes="tool-result-hint")

    def action_toggle_expand(self) -> None:
        """Toggle collapsed/expanded state via keyboard."""
        self._toggle_collapsed()

    def on_click(self, event) -> None:
        """Toggle collapsed/expanded state on click."""
        self._toggle_collapsed()

    def _toggle_collapsed(self) -> None:
        """Internal helper to toggle collapsed state."""
        has_content = self.result and (
            (hasattr(self.result, 'matches') and self.result.matches) or
            (hasattr(self.result, 'items') and self.result.items) or
            (hasattr(self.result, 'todos') and self.result.todos) or
            (isinstance(self.result, dict) and any(v not in ("", [], None) for v in self.result.values()))
        )
        if has_content:
            self.collapsed = not self.collapsed
            self.post_message(self.ToggleRequest(self.collapsed))


# =============================================================================
# BASH TOOL WIDGETS
# =============================================================================

class BashApprovalWidget(ToolApprovalWidget[BashArgs]):
    """Modern bash approval widget with clean visual hierarchy."""
    
    def compose(self) -> ComposeResult:
        command = self.args.command if isinstance(self.args, BaseModel) else self.args.get("command", "")
        is_background = self.args.is_background if isinstance(self.args, BaseModel) else self.args.get("is_background", False)
        
        yield NoMarkupStatic("bash", classes="approval-tool-name")
        yield Static("")  # Spacer
        yield Static(f"```bash\n{command}\n```", classes="approval-bash-command")
        
        if is_background:
            yield NoMarkupStatic("  ↳ background: yes", classes="approval-bash-param")


class BashResultWidget(ToolResultWidget[BashResult]):
    """Modern bash result widget with output display."""
    
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return
        
        stdout = self.result.stdout or ""
        stderr = self.result.stderr or ""
        lines = (stdout + stderr).strip().split("\n") if (stdout or stderr) else []
        line_count = len(lines)
        
        status = "Done" if self.success else "Error"
        status_class = "bash-success" if self.success else "bash-error"
        
        summary = f"└─ {status} ({line_count} lines)"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        
        yield NoMarkupStatic(summary, classes=f"tool-result-summary {status_class}")
        
        if not self.collapsed and lines:
            for line in lines[:15]:
                yield NoMarkupStatic(f"   {line}", classes="bash-output-line")
            
            if line_count > 15:
                remaining = line_count - 15
                yield NoMarkupStatic(f"   ... ({remaining} more lines)", classes="tool-result-hint")
        
        yield from self._footer()


# =============================================================================
# GREP TOOL WIDGETS
# =============================================================================

class GrepApprovalWidget(ToolApprovalWidget[GrepArgs]):
    """Modern grep approval widget with query type indicator."""
    
    def compose(self) -> ComposeResult:
        query = self.args.query if isinstance(self.args, BaseModel) else self.args.get("query", "")
        path = self.args.path if isinstance(self.args, BaseModel) else self.args.get("path", ".")
        is_regexp = self.args.is_regexp if isinstance(self.args, BaseModel) else self.args.get("is_regexp", False)
        max_matches = self.args.max_matches if isinstance(self.args, BaseModel) else self.args.get("max_matches", None)
        include_pattern = self.args.include_pattern if isinstance(self.args, BaseModel) else self.args.get("include_pattern", None)
        
        query_type = "regexp" if is_regexp else "literal"
        yield NoMarkupStatic(f"grep [{query_type}]", classes="approval-tool-name")
        yield Static("")
        yield NoMarkupStatic(f'"{query}"', classes="approval-grep-query")
        
        if path != ".":
            yield NoMarkupStatic(f"  ↳ path: {path}", classes="approval-grep-param")
        if max_matches:
            yield NoMarkupStatic(f"  ↳ max: {max_matches}", classes="approval-grep-param")
        if include_pattern:
            yield NoMarkupStatic(f"  ↳ filter: {include_pattern}", classes="approval-grep-param")


class GrepResultWidget(ToolResultWidget[GrepResult]):
    """Modern grep result widget with match display."""
    
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.matches:
            yield NoMarkupStatic("└─ no matches", classes="tool-result-muted")
            yield from self._footer()
            return
        
        matches = self.result.matches
        total = len(matches)
        
        summary = f"└─ {total} matches"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary")
        
        if not self.collapsed:
            max_show = 15
            for match in matches[:max_show]:
                file = match.file
                line = match.line
                content = match.content[:100] + "..." if len(match.content) > 100 else match.content
                yield Static(
                    f"   [ansi_bright_black]{file}[/][ansi_bright_black]:[/][ansi_bright_yellow]{line}[/][ansi_bright_black]:[/] {content}",
                    classes="tool-result-match"
                )
            
            if total > max_show:
                yield NoMarkupStatic(f"   ... ({total - max_show} more lines)", classes="tool-result-hint")
        
        yield from self._footer()


# =============================================================================
# LS TOOL WIDGETS
# =============================================================================

class LSApprovalWidget(ToolApprovalWidget[LSArgs]):
    """LS approval widget."""
    
    def compose(self) -> ComposeResult:
        path = self.args.path if isinstance(self.args, BaseModel) else self.args.get("path", ".")
        yield NoMarkupStatic("ls", classes="approval-tool-name")
        yield Static("")
        yield NoMarkupStatic(f"path: {path}", classes="approval-description")


class LSResultWidget(ToolResultWidget[LSResult]):
    """Modern ls result widget with file/directory listing."""
    
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.items:
            yield NoMarkupStatic("└─ empty directory", classes="tool-result-muted")
            yield from self._footer()
            return
        
        items = self.result.items
        total = len(items)
        
        summary = f"└─ {total} entries"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary")
        
        if not self.collapsed:
            max_show = 15
            for item in items[:max_show]:
                is_dir = item.endswith("/")
                item_class = "tool-result-ls-dir" if is_dir else "tool-result-ls-file"
                yield Static(f"   {item}", classes=f"tool-result-ls-item {item_class}")
            
            if total > max_show:
                yield NoMarkupStatic(f"   ... {total - max_show} more entries", classes="tool-result-ls-hint")
        
        yield from self._footer()


# =============================================================================
# FIND TOOL WIDGETS
# =============================================================================

class FindApprovalWidget(ToolApprovalWidget[FindArgs]):
    """Find approval widget."""
    
    def compose(self) -> ComposeResult:
        pattern = self.args.pattern if isinstance(self.args, BaseModel) else self.args.get("pattern", "")
        path = self.args.path if isinstance(self.args, BaseModel) else self.args.get("path", ".")
        
        yield NoMarkupStatic("find", classes="approval-tool-name")
        yield Static("")
        yield NoMarkupStatic(f'pattern: "{pattern}"', classes="approval-description")
        if path and path != ".":
            yield NoMarkupStatic(f"path: {path}", classes="approval-description")


class FindResultWidget(ToolResultWidget[FindResult]):
    """Modern find result widget with file listing."""
    
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.matches:
            yield NoMarkupStatic("└─ no files found", classes="tool-result-muted")
            yield from self._footer()
            return
        
        matches = self.result.matches
        total = len(matches)
        
        summary = f"└─ {total} files"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary")
        
        if not self.collapsed:
            max_show = 15
            for match in matches[:max_show]:
                is_dir = match.endswith("/")
                item_class = "tool-result-ls-dir" if is_dir else "tool-result-ls-file"
                display = _get_relative_path(match) if os.path.isabs(match) else match
                yield Static(f"   {display}", classes=f"tool-result-ls-item {item_class}")
            
            if total > max_show:
                yield NoMarkupStatic(f"   ... {total - max_show} more files", classes="tool-result-ls-hint")
        
        yield from self._footer()


# =============================================================================
# READ FILE TOOL WIDGETS
# =============================================================================

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
        
        lines = self.result.content.split("\n")
        line_count = len(lines)
        
        summary = f"└─ {line_count} lines loaded"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary tool-result-read-summary")
        
        if not self.collapsed:
            for warning in self.warnings:
                yield NoMarkupStatic(f"   {warning}", classes="tool-result-warning tool-result-read-warning")
            
            ext = Path(self.result.path).suffix.lstrip(".") or "text"
            content, remaining = _truncate_lines(self.result.content, 15)
            yield Static(f"```{ext}\n{content}\n```")
            if remaining:
                yield NoMarkupStatic(f"   ... ({remaining} more lines)", classes="tool-result-hint")
        
        yield from self._footer()


# =============================================================================
# WRITE FILE TOOL WIDGETS
# =============================================================================

class WriteFileApprovalWidget(ToolApprovalWidget[WriteFileArgs]):
    def compose(self) -> ComposeResult:
        file_path = getattr(self.args, "file_path", getattr(self.args, "filePath", "")) if isinstance(self.args, BaseModel) else self.args.get("file_path", self.args.get("filePath", ""))
        path = Path(file_path)
        file_extension = path.suffix.lstrip(".") or "text"
        content = self.args.content if isinstance(self.args, BaseModel) else self.args.get("content", "")

        yield NoMarkupStatic(f"File: {file_path}", classes="approval-description")
        yield Static("")
        yield Static(f"```{file_extension}\n{content}\n```")


class WriteFileResultWidget(ToolResultWidget[WriteFileResult]):
    def compose(self) -> ComposeResult:
        if not self.result:
            yield from self._footer()
            return
        
        summary = f"└─ {self.result.bytes_written} bytes written"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary")
        
        if not self.collapsed:
            ext = Path(self.result.path).suffix.lstrip(".") or "text"
            content, remaining = _truncate_lines(self.result.content, 15)
            yield Static(f"```{ext}\n{content}\n```")
            if remaining:
                yield NoMarkupStatic(f"   ... ({remaining} more lines)", classes="tool-result-hint")
        
        yield from self._footer()


# =============================================================================
# TODO TOOL WIDGETS
# =============================================================================

class TodoApprovalWidget(ToolApprovalWidget[TodoArgs]):
    def compose(self) -> ComposeResult:
        action = self.args.action if isinstance(self.args, BaseModel) else self.args.get("action", "")
        yield NoMarkupStatic(f"Action: {action}", classes="approval-description")
        todos = self.args.todos if isinstance(self.args, BaseModel) else self.args.get("todos", [])
        if todos:
            yield NoMarkupStatic(f"Todos: {len(todos)} items", classes="approval-description")


class TodoResultWidget(ToolResultWidget[TodoResult]):
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.todos:
            yield NoMarkupStatic("└─ no todos", classes="tool-result-muted")
            yield from self._footer()
            return

        total = len(self.result.todos)
        summary = f"└─ {total} items"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary")

        if not self.collapsed:
            by_status: dict[str, list] = {
                "in_progress": [],
                "pending": [],
                "completed": [],
                "cancelled": [],
            }
            for todo in self.result.todos:
                status = todo.status.value if hasattr(todo.status, "value") else str(todo.status)
                if status in by_status:
                    by_status[status].append(todo)

            for status in ["in_progress", "pending", "completed", "cancelled"]:
                for todo in by_status[status]:
                    yield NoMarkupStatic(f"   {todo.content}", classes=f"todo-{status}")
        
        yield from self._footer()


# =============================================================================
# ASK USER QUESTION WIDGETS
# =============================================================================

class AskUserQuestionResultWidget(ToolResultWidget[AskUserQuestionResult]):
    def compose(self) -> ComposeResult:
        if not self.result or not self.result.answers:
            yield NoMarkupStatic("└─ cancelled", classes="tool-result-muted")
            yield from self._footer()
            return

        total = len(self.result.answers)
        summary = f"└─ {total} answers"
        if self.collapsed:
            summary += " • Ctrl+O to expand"
        else:
            summary += " • Ctrl+O to collapse"
        yield NoMarkupStatic(summary, classes="tool-result-summary")

        if not self.collapsed:
            for answer in self.result.answers:
                if len(self.result.answers) > 1:
                    yield NoMarkupStatic(f"   Q: {answer.question}", classes="tool-result-detail")
                prefix = "(Other) " if answer.is_other else ""
                yield NoMarkupStatic(f"   A: {prefix}{answer.answer}", classes="ask-user-answer")
        
        yield from self._footer()


# =============================================================================
# WIDGET REGISTRY
# =============================================================================

APPROVAL_WIDGETS: dict[str, type[ToolApprovalWidget]] = {
    "bash": BashApprovalWidget,
    "read": ReadFileApprovalWidget,
    "read_file": ReadFileApprovalWidget,
    "write": WriteFileApprovalWidget,
    "write_file": WriteFileApprovalWidget,
    "edit": WriteFileApprovalWidget,
    "grep": GrepApprovalWidget,
    "find": FindApprovalWidget,
    "ls": LSApprovalWidget,
    "todo": TodoApprovalWidget,
}

RESULT_WIDGETS: dict[str, type[ToolResultWidget]] = {
    "bash": BashResultWidget,
    "read": ReadFileResultWidget,
    "read_file": ReadFileResultWidget,
    "write": WriteFileResultWidget,
    "write_file": WriteFileResultWidget,
    "edit": WriteFileResultWidget,
    "grep": GrepResultWidget,
    "ls": LSResultWidget,
    "find": FindResultWidget,
    "todo": TodoResultWidget,
    "ask_user_question": AskUserQuestionResultWidget,
}

ARGS_MODELS: dict[str, type[BaseModel]] = {
    "bash": BashArgs,
    "read": ReadFileArgs,
    "read_file": ReadFileArgs,
    "write": WriteFileArgs,
    "write_file": WriteFileArgs,
    "edit": WriteFileArgs,
    "grep": GrepArgs,
    "ls": LSArgs,
    "find": FindArgs,
    "todo": TodoArgs,
}


def get_approval_widget(tool_name: str, args: BaseModel | dict) -> ToolApprovalWidget:
    """Get the appropriate approval widget for a tool."""
    widget_class = APPROVAL_WIDGETS.get(tool_name, ToolApprovalWidget)
    if isinstance(args, dict):
        from pydantic import create_model
        args_model_cls = ARGS_MODELS.get(tool_name)
        if args_model_cls:
            args = args_model_cls(**args)
        else:
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
    """Get the appropriate result widget for a tool."""
    widget_class = RESULT_WIDGETS.get(tool_name, ToolResultWidget)
    
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
    elif tool_name == "find" and isinstance(result, list):
        result = FindResult(matches=result)
        
    return widget_class(result, success, message, collapsed, warnings)