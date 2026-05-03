from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from interface.textual_ui.cli_adapters import HookMessageSeverity

if TYPE_CHECKING:
    from interface.textual_ui.app import ChatScroll

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static
from textual.widgets._markdown import MarkdownStream

from interface.textual_ui.ansi_markdown import AnsiMarkdown as Markdown
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic


# Color constants for target design (ANSI escape sequences)
DIM_GRAY = "\x1b[38;2;140;140;140m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"
RESET = "\x1b[0m"
FG_MUTED = DIM_GRAY + DIM
FG_MUTED_ITALIC = DIM_GRAY + ITALIC + DIM


def _dim_text(text: str) -> str:
    """Apply dim gray styling to text."""
    return f"{FG_MUTED}{text}{RESET}"


def _dim_italic_text(text: str) -> str:
    """Apply dim gray italic styling to text."""
    return f"{FG_MUTED_ITALIC}{text}{RESET}"


class NonSelectableStatic(NoMarkupStatic):
    @property
    def text_selection(self) -> None:
        return None

    @text_selection.setter
    def text_selection(self, value: Any) -> None:
        pass

    def get_selection(self, selection: Any) -> None:
        return None


class ExpandingBorder(NonSelectableStatic):
    def render(self) -> str:
        height = self.size.height
        return "\n".join(["⎢"] * (height - 1) + ["⎣"])

    def on_resize(self) -> None:
        self.refresh()


class UserMessage(Static):
    def __init__(
        self, content: str, pending: bool = False, message_index: int | None = None
    ) -> None:
        super().__init__()
        self.add_class("user-message")
        self._content = content
        self._pending = pending
        self.message_index: int | None = message_index

    def get_content(self) -> str:
        return self._content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-message-container"):
            yield NoMarkupStatic(self._content, classes="user-message-content")
            if self._pending:
                self.add_class("pending")

    async def set_pending(self, pending: bool) -> None:
        if pending == self._pending:
            return

        self._pending = pending

        if pending:
            self.add_class("pending")
            return

        self.remove_class("pending")


class StreamingMessageBase(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content
        self._markdown: Markdown | None = None
        self._stream: MarkdownStream | None = None
        self._content_initialized = False
        self._to_write_buffer = ""
        self._indicator_widget: Static | None = None  # For compatibility
        self._is_spinning: bool = True

    def _get_markdown(self) -> Markdown:
        if self._markdown is None:
            raise RuntimeError(
                "Markdown widget not initialized. compose() must be called first."
            )
        return self._markdown

    def _ensure_stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = Markdown.get_stream(self._get_markdown())
        return self._stream

    def _is_chat_at_bottom(self) -> bool:
        try:
            chat = cast("ChatScroll", self.app.query_one("#chat"))
            return chat.is_at_bottom
        except Exception:
            return True

    async def append_content(self, content: str) -> None:
        if not content:
            return

        self._content += content

        if not self._should_write_content():
            return

        if self._is_chat_at_bottom():
            to_write = self._to_write_buffer + content
            self._to_write_buffer = ""
            stream = self._ensure_stream()
            await stream.write(to_write)
            return

        self._to_write_buffer += content

    async def write_initial_content(self) -> None:
        if self._content_initialized:
            return
        self._content_initialized = True
        if self._content and self._should_write_content():
            stream = self._ensure_stream()
            await stream.write(self._content)
            self._to_write_buffer = ""

    async def stop_stream(self) -> None:
        if self._to_write_buffer and self._should_write_content():
            stream = self._ensure_stream()
            await stream.write(self._to_write_buffer)
        self._to_write_buffer = ""

        if self._stream is None:
            return

        await self._stream.stop()
        self._stream = None

    def _should_write_content(self) -> bool:
        return True

    def get_content(self) -> str:
        return self._content

    def is_stripped_content_empty(self) -> bool:
        return self._content.strip() == ""


class AssistantMessage(StreamingMessageBase):
    """Assistant message with target design:
    ● Assistant response text here...
      continuation of text...
    """
    MARKER = "●"

    def __init__(self, content: str) -> None:
        super().__init__(content)
        self.add_class("assistant-message")
        self._is_spinning = True

    def compose(self) -> ComposeResult:
        markdown = Markdown("")
        self._markdown = markdown
        yield markdown

    def stop_spinning(self, success: bool = True) -> None:
        """Stop the spinning state, optionally update indicator."""
        self._is_spinning = False
        if self._indicator_widget:
            self._indicator_widget.update("●" if success else "●")


class ReasoningMessage(StreamingMessageBase):
    """Reasoning message with target design:
    ✽ Thinking
    └─ all thinking in it
    """
    MARKER = "✽"
    BRANCH = "└─"

    def __init__(self, content: str, collapsed: bool = False) -> None:
        super().__init__(content)
        self.add_class("reasoning-message")
        self.collapsed = collapsed
        self._indicator_widget: Static | None = None
        self._branch_widget: Static | None = None
        self._is_spinning = True

    def compose(self) -> ComposeResult:
        with Vertical(classes="reasoning-message-wrapper"):
            # Header line: ✽ Thinking
            with Horizontal(classes="reasoning-message-header"):
                self._indicator_widget = NonSelectableStatic(
                    self.MARKER, classes="reasoning-indicator"
                )
                yield self._indicator_widget
                yield NoMarkupStatic("Thinking", classes="reasoning-label")
            # Content line: └─ thinking content (on same line)
            markdown = Markdown("", classes="reasoning-message-content")
            markdown.display = not self.collapsed
            self._markdown = markdown
            with Horizontal(classes="reasoning-message-content-row"):
                self._branch_widget = NonSelectableStatic(
                    self.BRANCH, classes="reasoning-branch"
                )
                yield self._branch_widget
                yield markdown

    def stop_spinning(self, success: bool = True) -> None:
        """Stop the spinning state."""
        self._is_spinning = False

    def on_mount(self) -> None:
        pass

    def on_resize(self) -> None:
        pass


class TimingMessage(Static):
    """Timing message showing duration:
    ✻ Worked for 4s
    """
    MARKER = "✻"
    LABEL = "Worked for"

    def __init__(self, duration: float) -> None:
        super().__init__()
        self.add_class("timing-message")
        self._duration = duration

    def compose(self) -> ComposeResult:
        duration_str = self._format_duration()
        with Horizontal(classes="timing-container"):
            yield NonSelectableStatic(self.MARKER, classes="timing-indicator")
            yield NoMarkupStatic(f"{self.LABEL} {duration_str}", classes="timing-text")

    def _format_duration(self) -> str:
        if self._duration < 1:
            return f"{int(self._duration * 1000)}ms"
        elif self._duration < 60:
            return f"{int(self._duration)}s"
        else:
            minutes = int(self._duration // 60)
            seconds = int(self._duration % 60)
            return f"{minutes}m {seconds}s"


class UserCommandMessage(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.add_class("user-command-message")
        self._content = content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-command-container"):
            yield ExpandingBorder(classes="user-command-border")
            with Vertical(classes="user-command-content"):
                yield Markdown(self._content)


class WhatsNewMessage(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.add_class("whats-new-message")
        self._content = content

    def compose(self) -> ComposeResult:
        yield Markdown(self._content)


class InterruptMessage(Static):
    def __init__(self) -> None:
        super().__init__()
        self.add_class("interrupt-message")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="interrupt-container"):
            yield ExpandingBorder(classes="interrupt-border")
            yield NoMarkupStatic(
                "Interrupted · What should JARVIS do instead?",
                classes="interrupt-content",
            )


class BashOutputMessage(Static):
    def __init__(self, command: str, cwd: str, output: str, exit_code: int) -> None:
        super().__init__()
        self.add_class("bash-output-message")
        self._command = command
        self._cwd = cwd
        self._output = output.rstrip("\n")
        self._exit_code = exit_code

    def compose(self) -> ComposeResult:
        status_class = "bash-success" if self._exit_code == 0 else "bash-error"
        with Horizontal(classes="bash-command-line"):
            yield NonSelectableStatic("$ ", classes=f"bash-prompt {status_class}")
            yield NoMarkupStatic(self._command, classes="bash-command")
        with Horizontal(classes="bash-output-container"):
            yield ExpandingBorder(classes="bash-output-border")
            yield NoMarkupStatic(self._output, classes="bash-output")


class ErrorMessage(Static):
    def __init__(self, error: str, collapsed: bool = False) -> None:
        super().__init__()
        self.add_class("error-message")
        self._error = error
        self.collapsed = collapsed
        self._content_widget: Static | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="error-container"):
            yield ExpandingBorder(classes="error-border")
            self._content_widget = NoMarkupStatic(
                f"Error: {self._error}", classes="error-content"
            )
            yield self._content_widget

    def set_collapsed(self, collapsed: bool) -> None:
        pass


class HookRunContainer(Vertical):
    def __init__(self) -> None:
        super().__init__(classes="hook-run-container")
        self.display = False

    async def add_message(self, widget: HookSystemMessageLine) -> None:
        await self.mount(widget)
        self.display = True


_HOOK_SEVERITY_ICONS: dict[HookMessageSeverity, str] = {
    HookMessageSeverity.OK: "✓",
    HookMessageSeverity.WARNING: "⚠",
    HookMessageSeverity.ERROR: "✗",
}


class HookSystemMessageLine(Static):
    def __init__(
        self,
        hook_name: str,
        content: str,
        severity: HookMessageSeverity = HookMessageSeverity.WARNING,
    ) -> None:
        super().__init__()
        self.add_class("hook-system-message")
        self.add_class(f"hook-severity-{severity}")
        self._hook_name = hook_name
        self._content = content
        self._severity = severity

    def compose(self) -> ComposeResult:
        icon = _HOOK_SEVERITY_ICONS.get(
            self._severity, _HOOK_SEVERITY_ICONS[HookMessageSeverity.WARNING]
        )
        with Horizontal(classes="hook-system-container"):
            yield NonSelectableStatic(icon, classes="hook-system-icon")
            yield NoMarkupStatic(
                f"[{self._hook_name}] {self._content}", classes="hook-system-content"
            )


class WarningMessage(Static):
    def __init__(self, message: str, show_border: bool = True) -> None:
        super().__init__()
        self.add_class("warning-message")
        self._message = message
        self._show_border = show_border

    def compose(self) -> ComposeResult:
        with Horizontal(classes="warning-container"):
            if self._show_border:
                yield ExpandingBorder(classes="warning-border")
            yield NoMarkupStatic(self._message, classes="warning-content")