from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from core.tools.permissions import RequiredPermission
from interface.textual_ui.cli_adapters import VibeConfig
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.tool_widgets import get_approval_widget


# Tool risk classification
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

TOOL_RISK_LEVELS: dict[str, str] = {
    "read": RISK_LOW,
    "read_file": RISK_LOW,
    "ls": RISK_LOW,
    "find": RISK_LOW,
    "grep": RISK_LOW,
    "bash": RISK_MEDIUM,
    "edit": RISK_HIGH,
    "edit_file": RISK_HIGH,
    "str_replace_editor": RISK_HIGH,
    "write": RISK_HIGH,
    "write_file": RISK_HIGH,
}

RISK_STYLES: dict[str, dict[str, str]] = {
    RISK_LOW: {"icon": "🟢", "label": "LOW RISK", "border": "success"},
    RISK_MEDIUM: {"icon": "🟡", "label": "MEDIUM RISK", "border": "warning"},
    RISK_HIGH: {"icon": "🔴", "label": "HIGH RISK", "border": "error"},
}


def get_tool_risk(tool_name: str) -> str:
    return TOOL_RISK_LEVELS.get(tool_name, RISK_MEDIUM)


def is_inline_approval(tool_name: str) -> bool:
    """Whether this tool should use the compact inline approval bar."""
    return get_tool_risk(tool_name) == RISK_LOW


class InlineApprovalBar(Container):
    """Compact inline approval bar for low-risk tools.

    Rendered as:
      🟢 LOW RISK  📄 READ src/main.py  [Y]es  [A]lways  [N]o
    """

    can_focus = True
    can_focus_children = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "approve", "Yes", show=False),
        Binding("a", "approve_always", "Always", show=False),
        Binding("n", "reject", "No", show=False),
        Binding("escape", "reject", "Reject", show=False),
    ]

    class Approved(Message):
        def __init__(self, tool_name: str, tool_args: BaseModel) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.tool_args = tool_args

    class ApprovedAlways(Message):
        def __init__(
            self,
            tool_name: str,
            tool_args: BaseModel,
            required_permissions: list[RequiredPermission],
        ) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.tool_args = tool_args
            self.required_permissions = required_permissions

    class Rejected(Message):
        def __init__(self, tool_name: str, tool_args: BaseModel) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.tool_args = tool_args

    def __init__(
        self,
        tool_name: str,
        tool_args: BaseModel,
        required_permissions: list[RequiredPermission] | None = None,
    ) -> None:
        super().__init__(classes="inline-approval-bar")
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.required_permissions = required_permissions or []
        self._summary = self._build_summary()

    def _build_summary(self) -> str:
        """Build compact tool summary for the bar."""
        args = self.tool_args
        if isinstance(args, dict):
            for key in ("files", "path", "filePath", "command", "pattern", "query"):
                val = args.get(key)
                if val:
                    text = str(val)
                    if isinstance(val, list):
                        text = f"{len(val)} file{'s' if len(val) != 1 else ''}"
                    elif len(text) > 50:
                        text = text[:47] + "…"
                    return text
        elif hasattr(args, "model_fields"):
            for key in ("files", "path", "file_path", "command", "pattern", "query"):
                val = getattr(args, key, None)
                if val:
                    text = str(val)
                    if isinstance(val, list):
                        text = f"{len(val)} file{'s' if len(val) != 1 else ''}"
                    elif len(text) > 50:
                        text = text[:47] + "…"
                    return text
        return ""

    def compose(self) -> ComposeResult:
        risk = get_tool_risk(self.tool_name)
        style = RISK_STYLES[risk]

        with Horizontal(classes="inline-approval-content"):
            yield NoMarkupStatic(
                f"{style['icon']} {style['label']}", classes="inline-approval-risk"
            )
            tool_label = self.tool_name.upper() if len(self.tool_name) <= 6 else self.tool_name.title()
            summary = f"{tool_label}"
            if self._summary:
                summary += f"  {self._summary}"
            yield NoMarkupStatic(summary, classes="inline-approval-tool")
            yield NoMarkupStatic("[Y]es", classes="inline-approval-btn inline-approval-yes")
            yield NoMarkupStatic("[A]lways", classes="inline-approval-btn inline-approval-always")
            yield NoMarkupStatic("[N]o", classes="inline-approval-btn inline-approval-no")

    def on_mount(self) -> None:
        self.focus()

    def action_approve(self) -> None:
        self.post_message(self.Approved(tool_name=self.tool_name, tool_args=self.tool_args))

    def action_approve_always(self) -> None:
        self.post_message(
            self.ApprovedAlways(
                tool_name=self.tool_name,
                tool_args=self.tool_args,
                required_permissions=self.required_permissions,
            )
        )

    def action_reject(self) -> None:
        self.post_message(self.Rejected(tool_name=self.tool_name, tool_args=self.tool_args))

    def on_blur(self, event: events.Blur) -> None:
        self.call_after_refresh(self._refocus_if_needed)

    def _refocus_if_needed(self) -> None:
        if self.has_focus:
            return
        if self.is_mounted and self.display and not self._closing:
            self.focus()


class ApprovalApp(Container):
    can_focus = True
    can_focus_children = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("1", "select_1", "Yes", show=False),
        Binding("y", "select_1", "Yes", show=False),
        Binding("2", "select_2", "Always Tool Session", show=False),
        Binding("3", "select_3", "No", show=False),
        Binding("n", "select_3", "No", show=False),
        Binding("escape", "reject", "Reject", show=False),
    ]

    class ApprovalGranted(Message):
        def __init__(self, tool_name: str, tool_args: BaseModel) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.tool_args = tool_args

    class ApprovalGrantedAlwaysTool(Message):
        def __init__(
            self,
            tool_name: str,
            tool_args: BaseModel,
            required_permissions: list[RequiredPermission],
        ) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.tool_args = tool_args
            self.required_permissions = required_permissions

    class ApprovalRejected(Message):
        def __init__(self, tool_name: str, tool_args: BaseModel) -> None:
            super().__init__()
            self.tool_name = tool_name
            self.tool_args = tool_args

    def __init__(
        self,
        tool_name: str,
        tool_args: BaseModel,
        config: VibeConfig,
        required_permissions: list[RequiredPermission] | None = None,
    ) -> None:
        super().__init__(id="approval-app")
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.config = config
        self.required_permissions = required_permissions or []
        self.selected_option = 0
        self.content_container: Vertical | None = None
        self.title_widget: Static | None = None
        self.risk_widget: Static | None = None
        self.tool_info_container: Vertical | None = None
        self.option_widgets: list[Static] = []
        self.help_widget: Static | None = None

    def compose(self) -> ComposeResult:
        risk = get_tool_risk(self.tool_name)
        style = RISK_STYLES[risk]

        with Vertical(id="approval-options"):
            yield NoMarkupStatic("")
            for _ in range(3):
                widget = NoMarkupStatic("", classes="approval-option")
                self.option_widgets.append(widget)
                yield widget
            yield NoMarkupStatic("")
            self.help_widget = NoMarkupStatic(
                "↑↓ navigate  1-3/y/n direct  Enter select  ESC reject", classes="approval-help"
            )
            yield self.help_widget

        with Vertical(id="approval-content"):
            # Risk badge + title on same line
            with Horizontal(classes="approval-title-row"):
                self.risk_widget = NoMarkupStatic(
                    f"{style['icon']} {style['label']}", classes="approval-risk-badge"
                )
                self.risk_widget.add_class(f"approval-risk-{risk}")
                yield self.risk_widget
                self.title_widget = NoMarkupStatic(
                    f"Approval required: {self.tool_name}", classes="approval-title"
                )
                yield self.title_widget

            with VerticalScroll(classes="approval-tool-info-scroll"):
                self.tool_info_container = Vertical(
                    classes="approval-tool-info-container"
                )
                yield self.tool_info_container

    async def on_mount(self) -> None:
        # Apply risk-based border styling
        risk = get_tool_risk(self.tool_name)
        style = RISK_STYLES[risk]
        border_var = style["border"]
        # Map to CSS class for the border color
        if border_var == "error":
            self.add_class("approval-border-high")
        elif border_var == "warning":
            self.add_class("approval-border-medium")
        else:
            self.add_class("approval-border-low")

        await self._update_tool_info()
        self._update_options()
        self.focus()

    async def _update_tool_info(self) -> None:
        if not self.tool_info_container:
            return

        approval_widget = get_approval_widget(self.tool_name, self.tool_args)
        await self.tool_info_container.remove_children()
        await self.tool_info_container.mount(approval_widget)

    def _update_options(self) -> None:
        if self.required_permissions:
            labels = ", ".join(rp.label for rp in self.required_permissions)
            always_text = f"Yes and always allow for this session: {labels}"
        else:
            always_text = f"Yes and always allow {self.tool_name} for this session"

        options = [
            ("Yes", "yes"),
            (always_text, "yes"),
            ("No and tell the agent what to do instead", "no"),
        ]

        for idx, ((text, color_type), widget) in enumerate(
            zip(options, self.option_widgets, strict=True)
        ):
            is_selected = idx == self.selected_option

            cursor = "› " if is_selected else "  "
            option_text = f"{cursor}{idx + 1}. {text}"

            widget.update(option_text)

            widget.remove_class("approval-cursor-selected")
            widget.remove_class("approval-option-selected")
            widget.remove_class("approval-option-yes")
            widget.remove_class("approval-option-no")

            if is_selected:
                widget.add_class("approval-cursor-selected")
                if color_type == "yes":
                    widget.add_class("approval-option-yes")
                else:
                    widget.add_class("approval-option-no")
            else:
                widget.add_class("approval-option-selected")
                if color_type == "yes":
                    widget.add_class("approval-option-yes")
                else:
                    widget.add_class("approval-option-no")

    def action_move_up(self) -> None:
        self.selected_option = (self.selected_option - 1) % 3
        self._update_options()

    def action_move_down(self) -> None:
        self.selected_option = (self.selected_option + 1) % 3
        self._update_options()

    def action_select(self) -> None:
        self._handle_selection(self.selected_option)

    def action_select_1(self) -> None:
        self.selected_option = 0
        self._handle_selection(0)

    def action_select_2(self) -> None:
        self.selected_option = 1
        self._handle_selection(1)

    def action_select_3(self) -> None:
        self.selected_option = 2
        self._handle_selection(2)

    def action_reject(self) -> None:
        self.selected_option = 2
        self._handle_selection(2)

    def _handle_selection(self, option: int) -> None:
        match option:
            case 0:
                self.post_message(
                    self.ApprovalGranted(
                        tool_name=self.tool_name, tool_args=self.tool_args
                    )
                )
            case 1:
                self.post_message(
                    self.ApprovalGrantedAlwaysTool(
                        tool_name=self.tool_name,
                        tool_args=self.tool_args,
                        required_permissions=self.required_permissions,
                    )
                )
            case 2:
                self.post_message(
                    self.ApprovalRejected(
                        tool_name=self.tool_name, tool_args=self.tool_args
                    )
                )

    def on_blur(self, event: events.Blur) -> None:
        # Refocus if needed to prevent getting stuck without keyboard control
        self.call_after_refresh(self._refocus_if_needed)

    def _refocus_if_needed(self) -> None:
        if self.has_focus:
            return
        # Only refocus if we are still visible and part of the DOM
        if self.is_mounted and self.display and not self.is_closing:
            self.focus()

    @property
    def is_closing(self) -> bool:
        """Check if the widget is in the process of being removed."""
        return not self.is_mounted or self._closing

