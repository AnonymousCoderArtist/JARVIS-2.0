"""Configuration menu widget for selecting different config sections."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Vertical
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic


class ConfigMenuOption:
    """Configuration menu option kinds."""
    GENERAL = "general"
    MCP_SERVERS = "mcp_servers"
    MCP_TOOLS = "mcp_tools"
    TOOLS = "tools"


class ConfigMenuApp(Container):
    """Configuration menu with navigatable option picker."""

    can_focus_children = True

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close", "Close", show=False),
    ]

    class ConfigSectionSelected(Message):
        """Posted when a config section is selected."""

        def __init__(self, section: str) -> None:
            super().__init__()
            self.section = section

    def __init__(self, mcp_server_count: int = 0, mcp_tool_count: int = 0, tool_count: int = 0) -> None:
        super().__init__(id="config-menu-app")
        self._mcp_server_count = mcp_server_count
        self._mcp_tool_count = mcp_tool_count
        self._tool_count = tool_count

    def _get_general_option_text(self) -> Text:
        text = Text(no_wrap=True)
        text.append("⚙️ General Settings", style="bold")
        text.append(" - Model, thinking, preferences", style="dim")
        return text

    def _get_mcp_servers_option_text(self) -> Text:
        text = Text(no_wrap=True)
        text.append("🔌 MCP Servers", style="bold")
        if self._mcp_server_count > 0:
            text.append(f" ({self._mcp_server_count} configured)", style="dim")
        else:
            text.append(" (none configured)", style="dim")
        return text

    def _get_mcp_tools_option_text(self) -> Text:
        text = Text(no_wrap=True)
        text.append("🛠️ MCP Tools", style="bold")
        if self._mcp_tool_count > 0:
            text.append(f" ({self._mcp_tool_count} tools)", style="dim")
        else:
            text.append(" (no tools)", style="dim")
        return text

    def _get_tools_option_text(self) -> Text:
        text = Text(no_wrap=True)
        text.append("📦 All Tools", style="bold")
        if self._tool_count > 0:
            text.append(f" ({self._tool_count} available)", style="dim")
        else:
            text.append(" (none)", style="dim")
        return text

    def compose(self) -> ComposeResult:
        options: list[Option] = [
            Option(self._get_general_option_text(), id=ConfigMenuOption.GENERAL),
            Option(self._get_mcp_servers_option_text(), id=ConfigMenuOption.MCP_SERVERS),
            Option(self._get_mcp_tools_option_text(), id=ConfigMenuOption.MCP_TOOLS),
            Option(self._get_tools_option_text(), id=ConfigMenuOption.TOOLS),
        ]

        with Vertical(id="config-menu-content"):
            yield NoMarkupStatic("Configuration", classes="config-menu-title")
            yield NoMarkupStatic("")
            yield OptionList(*options, id="config-menu-options")
            yield NoMarkupStatic("")
            yield NoMarkupStatic(
                "↑↓ Navigate  Enter Select  Esc Close", classes="config-menu-help"
            )

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if not option_id:
            return

        self.post_message(self.ConfigSectionSelected(section=option_id))

    def update_counts(self, mcp_server_count: int, mcp_tool_count: int, tool_count: int) -> None:
        """Update the display with new counts."""
        self._mcp_server_count = mcp_server_count
        self._mcp_tool_count = mcp_tool_count
        self._tool_count = tool_count
        self._refresh_options()

    def _refresh_options(self) -> None:
        option_list = self.query_one(OptionList)
        option_list.replace_option_prompt(
            ConfigMenuOption.GENERAL, self._get_general_option_text()
        )
        option_list.replace_option_prompt(
            ConfigMenuOption.MCP_SERVERS, self._get_mcp_servers_option_text()
        )
        option_list.replace_option_prompt(
            ConfigMenuOption.MCP_TOOLS, self._get_mcp_tools_option_text()
        )
        option_list.replace_option_prompt(
            ConfigMenuOption.TOOLS, self._get_tools_option_text()
        )