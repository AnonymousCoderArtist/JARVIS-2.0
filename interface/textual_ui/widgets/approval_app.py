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

RISK_REASONS: dict[str, str] = {
    "bash": "Executes shell commands on your system",
    "edit": "Modifies existing file contents",
    "edit_file": "Modifies existing file contents",
    "str_replace_editor": "Modifies existing file contents",
    "write": "Creates or overwrites files",
    "write_file": "Creates or overwrites files",
    "read": "Reads file contents (read-only)",
    "read_file": "Reads file contents (read-only)",
    "ls": "Lists directory contents (read-only)",
    "find": "Searches for files (read-only)",
    "grep": "Searches file contents (read-only)",
}

TOOL_ICONS: dict[str, str] = {
    "read": "📄",
    "read_file": "📄",
    "write": "📝",
    "write_file": "📝",
    "edit": "✏️",
    "edit_file": "✏️",
    "str_replace_editor": "✏️",
    "ls": "📁",
    "find": "🔍",
    "grep": "🔎",
    "bash": "⚡",
}


def get_tool_risk(tool_name: str) -> str:
    return TOOL_RISK_LEVELS.get(tool_name, RISK_MEDIUM)


def get_tool_icon(tool_name: str) -> str:
    return TOOL_ICONS.get(tool_name, "●")


def get_risk_reason(tool_name: str) -> str:
    return RISK_REASONS.get(tool_name, "This tool requires your approval")


def is_inline_approval(tool_name: str) -> bool:
    """Whether this tool should use the compact inline approval bar."""
    return get_tool_risk(tool_name) == RISK_LOW


def _build_tool_summary(tool_args: BaseModel | dict, tool_name: str) -> str:
    """Build a human-readable summary of what the tool will do."""
    icon = get_tool_icon(tool_name)

    primary = ""
    args = tool_args
    if isinstance(args, dict):
        for key in ("files", "path", "filePath", "command", "pattern", "query"):
            val = args.get(key)
            if val:
                if isinstance(val, list):
                    primary = f"{len(val)} file{'s' if len(val) != 1 else ''}"
                else:
                    text = str(val)
                    primary = text[:47] + "…" if len(text) > 50 else text
                break
    elif hasattr(args, "model_fields"):
        for key in ("files", "path", "file_path", "command", "pattern", "query"):
            val = getattr(args, key, None)
            if val:
                if isinstance(val, list):
                    primary = f"{len(val)} file{'s' if len(val) != 1 else ''}"
                else:
                    text = str(val)
                    primary = text[:47] + "…" if len(text) > 50 else text
                break

    action_map = {
        "read": "Read", "read_file": "Read",
        "write": "Write", "write_file": "Write",
        "edit": "Edit", "edit_file": "Edit", "str_replace_editor": "Edit",
        "bash": "Run command",
        "grep": "Search", "find": "Find", "ls": "List",
    }
    action = action_map.get(tool_name, tool_name.title())

    if primary:
        return f"{icon} {action} {primary}"
    return f"{icon} {action}"


class InlineApprovalBar(Container):
    """Compact inline approval bar for low-risk tools.

    Rendered as:
      🟢 LOW RISK  📄 Read src/main.py  [Y]es  [A]lways  [N]o
    """

    can_focus = True
    can_focus_children = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "approve", "Yes", show=False),
        Binding("a", "approve_always", "Always", show=False),
        Binding("n", "reject", "No", show=False),
        Binding("s", "reject", "Skip", show=False),
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
        session_rules_count: int = 0,
    ) -> None:
        super().__init__(classes="inline-approval-bar")
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.required_permissions = required_permissions or []
        self.session_rules_count = session_rules_count
        self._summary = _build_tool_summary(tool_args, tool_name)

    def compose(self) -> ComposeResult:
        risk = get_tool_risk(self.tool_name)
        style = RISK_STYLES[risk]

        with Horizontal(classes="inline-approval-content"):
            yield NoMarkupStatic(
                f"{style['icon']} {style['label']}", classes="inline-approval-risk"
            )
            yield NoMarkupStatic(self._summary, classes="inline-approval-tool")
            yield NoMarkupStatic("[Y]es", classes="inline-approval-btn inline-approval-yes")
            yield NoMarkupStatic("[A]lways", classes="inline-approval-btn inline-approval-always")
            yield NoMarkupStatic("[N]o", classes="inline-approval-btn inline-approval-no")
            if self.session_rules_count > 0:
                yield NoMarkupStatic(
                    f"🔒 {self.session_rules_count} rule{'s' if self.session_rules_count != 1 else ''}",
                    classes="inline-approval-rules",
                )

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


# Action card definitions for ApprovalApp
class _ActionCard:
    """Defines a single approval action card."""

    def __init__(
        self,
        icon: str,
        label: str,
        description: str,
        key: str,
        color_type: str,
    ) -> None:
        self.icon = icon
        self.label = label
        self.description = description
        self.key = key
        self.color_type = color_type


def _get_action_cards(
    tool_name: str,
    required_permissions: list[RequiredPermission],
) -> list[_ActionCard]:
    """Build the list of action cards for the approval screen."""
    if required_permissions:
        labels = ", ".join(rp.label for rp in required_permissions)
        always_desc = f"Auto-approve for this session: {labels}"
    else:
        always_desc = f"Auto-approve {tool_name} for this session"

    return [
        _ActionCard(
            icon="✓",
            label="Approve",
            description="Allow this tool execution once",
            key="Y",
            color_type="yes",
        ),
        _ActionCard(
            icon="∞",
            label="Always Approve",
            description=always_desc,
            key="A",
            color_type="yes",
        ),
        _ActionCard(
            icon="✗",
            label="Reject",
            description="Deny and tell the agent what to do instead",
            key="N",
            color_type="no",
        ),
    ]


class ApprovalApp(Container):
    """Modern approval interface with action cards, risk indicators, and session rules.

    Layout:
    ┌─────────────────────────────────────────────────┐
    │ 🔴 HIGH RISK  │  ✏️ Edit                       │
    │ Modifies existing file contents                 │
    │ 🔒 accessing sensitive files (edit)             │
    ├─────────────────────────────────────────────────┤
    │ Tool info (diff, command, etc.)                 │
    ├─────────────────────────────────────────────────┤
    │ ▸ 1. ✓ Approve          Allow once         [Y] │
    │   2. ∞ Always Approve   Auto-approve ...    [A] │
    │   3. ✗ Reject           Deny and ...       [N] │
    ├─────────────────────────────────────────────────┤
    │ ↑↓ 1-3  Enter  Esc          🔒 3 session rules │
    └─────────────────────────────────────────────────┘
    """

    can_focus = True
    can_focus_children = False

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("1", "select_1", "Yes", show=False),
        Binding("y", "select_1", "Yes", show=False),
        Binding("2", "select_2", "Always", show=False),
        Binding("a", "select_2", "Always", show=False),
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
        session_rules_count: int = 0,
    ) -> None:
        super().__init__(id="approval-app")
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.config = config
        self.required_permissions = required_permissions or []
        self.session_rules_count = session_rules_count
        self.selected_option = 0
        self.tool_info_container: Vertical | None = None
        self.option_widgets: list[Static] = []
        self.help_widget: Static | None = None
        self.rules_widget: Static | None = None
        self._action_cards = _get_action_cards(tool_name, self.required_permissions)

    def compose(self) -> ComposeResult:
        risk = get_tool_risk(self.tool_name)
        style = RISK_STYLES[risk]
        icon = get_tool_icon(self.tool_name)
        reason = get_risk_reason(self.tool_name)

        with Vertical(id="approval-content"):
            # Header: risk badge + tool icon/name + reason
            with Vertical(classes="approval-header"):
                with Horizontal(classes="approval-title-row"):
                    risk_widget = NoMarkupStatic(
                        f"{style['icon']} {style['label']}", classes="approval-risk-badge"
                    )
                    risk_widget.add_class(f"approval-risk-{risk}")
                    yield risk_widget
                    yield NoMarkupStatic(
                        f"{icon} {self.tool_name}", classes="approval-tool-name"
                    )
                yield NoMarkupStatic(reason, classes="approval-risk-reason")

                # Permission chips
                if self.required_permissions:
                    with Horizontal(classes="approval-permission-chips"):
                        for perm in self.required_permissions:
                            yield NoMarkupStatic(
                                f"🔒 {perm.label}", classes="approval-permission-chip"
                            )

            # Tool detail area (diff, command preview, etc.)
            with VerticalScroll(classes="approval-tool-info-scroll"):
                self.tool_info_container = Vertical(
                    classes="approval-tool-info-container"
                )
                yield self.tool_info_container

        # Action cards + help + session rules
        with Vertical(id="approval-options"):
            for _ in self._action_cards:
                widget = NoMarkupStatic("", classes="approval-action-card")
                self.option_widgets.append(widget)
                yield widget

            with Horizontal(classes="approval-footer-row"):
                self.help_widget = NoMarkupStatic(
                    "↑↓ navigate   [1-3] select   Enter confirm   Esc reject",
                    classes="approval-help",
                )
                yield self.help_widget
                rules_text = f"🔒 {self.session_rules_count} rule{'s' if self.session_rules_count != 1 else ''}"
                self.rules_widget = NoMarkupStatic(rules_text, classes="approval-session-rules")
                yield self.rules_widget

    async def on_mount(self) -> None:
        risk = get_tool_risk(self.tool_name)
        style = RISK_STYLES[risk]
        border_var = style["border"]
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
        for idx, (card, widget) in enumerate(
            zip(self._action_cards, self.option_widgets, strict=True)
        ):
            is_selected = idx == self.selected_option

            cursor = "▸ " if is_selected else "  "
            option_text = (
                f"{cursor}{idx + 1}. {card.icon} {card.label}"
                f"  {card.description}  [{card.key}]"
            )

            widget.update(option_text)

            widget.remove_class("approval-card-selected")
            widget.remove_class("approval-card-unselected")
            widget.remove_class("approval-card-yes")
            widget.remove_class("approval-card-no")

            if is_selected:
                widget.add_class("approval-card-selected")
                widget.add_class(f"approval-card-{card.color_type}")
            else:
                widget.add_class("approval-card-unselected")
                widget.add_class(f"approval-card-{card.color_type}")

    def action_move_up(self) -> None:
        self.selected_option = (self.selected_option - 1) % len(self._action_cards)
        self._update_options()

    def action_move_down(self) -> None:
        self.selected_option = (self.selected_option + 1) % len(self._action_cards)
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
        self.call_after_refresh(self._refocus_if_needed)

    def _refocus_if_needed(self) -> None:
        if self.has_focus:
            return
        if self.is_mounted and self.display and not self.is_closing:
            self.focus()

    @property
    def is_closing(self) -> bool:
        """Check if the widget is in the process of being removed."""
        return not self.is_mounted or self._closing
