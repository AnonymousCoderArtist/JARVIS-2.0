"""OpenTUI application for JARVIS."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from opentui import (
        Signal,
        component,
        render,
        use_keyboard,
        use_renderer,
        Box,
        Text,
        ScrollBox,
        Show,
        For,
        Bold,
    )
    OPENTUI_AVAILABLE = True
except ImportError:
    # Fallback for when opentui is not installed
    OPENTUI_AVAILABLE = False
    # These will remain None but we won't use them if opentui is not available
    Signal = None
    component = None
    render = None
    use_keyboard = None
    use_renderer = None
    Box = None
    Text = None
    ScrollBox = None
    Show = None
    For = None
    Bold = None

logger = logging.getLogger(__name__)


# Only create signals and components if opentui is available
if OPENTUI_AVAILABLE:
    # Signal-based state
    messages = Signal([], name="messages")
    current_input = Signal("", name="current_input")
    is_processing = Signal(False, name="is_processing")
    current_profile = Signal("default", name="current_profile")
    show_help = Signal(False, name="show_help")

    @dataclass
    class Message:
        """Represents a chat message."""
        role: str  # "user" or "assistant"
        content: str
        timestamp: datetime = field(default_factory=datetime.now)
        tool_calls: list[dict] = field(default_factory=list)


    def add_message(role: str, content: str, tool_calls: list[dict] | None = None) -> None:
        """Add a message to the message list."""
        with messages.lock():
            current = messages()
            current.append(Message(
                role=role,
                content=content,
                tool_calls=tool_calls or []
            ))
            messages.set(current)


    def clear_input() -> None:
        """Clear the current input."""
        current_input.set("")


    @component
    def Header():
        """Top header with title and profile info."""
        return Box(
            Text(
                Bold("🤖 JARVIS v2.0 (OpenTUI)"),
                fg="#00ff00",
            ),
            Text(
                lambda: f"Profile: {current_profile()}",
                fg="#888888",
            ),
            padding=1,
            border=True,
            border_fg="#00ff00",
            gap=1,
        )


    @component
    def MessageItem(message: Message):
        """Display a single message."""
        role_color = "#00ffff" if message.role == "user" else "#ffaa00"
        role_label = "👤 You" if message.role == "user" else "🤖 JARVIS"
        
        # Format timestamp
        ts = message.timestamp.strftime("%H:%M:%S")
        
        return Box(
            Text(f"{role_label} [{ts}]", fg=role_color, bold=True),
            Text(message.content, wrap=True),
            padding=1,
            border=True,
            border_fg=role_color,
            gap=0,
        )


    @component
    def MessageList():
        """Scrollable list of messages."""
        return ScrollBox(
            For(
                lambda msg, idx: MessageItem(msg),
                each=messages,
            ),
            border=True,
            border_fg="#444444",
            flex=1,
        )


    @component
    def InputArea():
        """Input area for user messages."""
        return Box(
            Text(
                lambda: f"> {current_input()}" if current_input() else "> ",
                fg="#00ff00",
            ),
            Text("Enter: send | Ctrl+L: clear | Ctrl+H: help | Ctrl+Q: quit", fg="#666666", size=0.8),
            padding=1,
            border=True,
            border_fg="#00ff00",
            gap=0,
        )


    @component
    def StatusBar():
        """Bottom status bar."""
        return Box(
            Text(
                lambda: "🔄 Processing..." if is_processing() else "✅ Ready",
                fg="#888888",
            ),
            Text(
                lambda: f"Messages: {len(messages())}",
                fg="#666666",
            ),
            padding=1,
            border=True,
            border_fg="#444444",
            gap=1,
        )


    @component
    def HelpOverlay():
        """Help overlay when triggered."""
        return Box(
            Text(Bold("Keyboard Shortcuts:"), fg="#ffff00"),
            Text("  Enter  - Send message", fg="#cccccc"),
            Text("  Ctrl+L - Clear all messages", fg="#cccccc"),
            Text("  Ctrl+C - Cancel input", fg="#cccccc"),
            Text("  Ctrl+P - Cycle profile", fg="#cccccc"),
            Text("  Ctrl+H - Toggle help", fg="#cccccc"),
            Text("  Ctrl+Q - Quit", fg="#cccccc"),
            padding=2,
            border=True,
            border_fg="#ffff00",
            gap=0,
        )


    @component
    def App():
        """Main application component."""
        return Box(
            Header(),
            MessageList(),
            InputArea(),
            StatusBar(),
            Show(HelpOverlay(), when=show_help),
            flex_direction="column",
            gap=1,
        )


    # Global references to be set by run_opentui_ui
    _jarvis_agent = None
    _tool_registry = None
    _agent_manager = None
    _async_agent_manager = None


    async def process_user_message(text: str) -> None:
        """Process user message through the JARVIS agent."""
        global _jarvis_agent, _tool_registry, _agent_manager, _async_agent_manager
        
        is_processing.set(True)
        
        try:
            if _jarvis_agent is None:
                add_message("assistant", "Error: Agent not initialized")
                return
            
            # Add thinking indicator
            add_message("assistant", "🤔 Thinking...")
            
            # Process through JARVIS agent
            response = await _jarvis_agent.process(text, context={})
            
            # Remove the thinking indicator and add the actual response
            with messages.lock():
                msg_list = messages()
                if msg_list and msg_list[-1].content == "🤔 Thinking...":
                    msg_list.pop()
                msg_list.append(Message(
                    role="assistant",
                    content=response,
                    timestamp=datetime.now()
                ))
                messages.set(msg_list)
                
        except Exception as e:
            add_message("assistant", f"Error: {str(e)}")
            logger.exception("Error processing message")
        finally:
            is_processing.set(False)


    def handle_keyboard(event) -> None:
        """Global keyboard handler."""
        text = current_input().strip()
        
        if event.name == "enter":
            # Submit message
            if text and not is_processing():
                add_message("user", text)
                clear_input()
                asyncio.create_task(process_user_message(text))
        elif event.name == "backspace":
            # Handle backspace - remove last character
            if text:
                current_input.set(text[:-1])
        elif event.name == "space":
            # Add space
            current_input.set(text + " ")
        elif hasattr(event, "text") and event.text:
            # Add character input
            current_input.set(text + event.text)
        elif event.name == "c" and event.ctrl:
            # Ctrl+C to cancel/clear input
            clear_input()
        elif event.name == "l" and event.ctrl:
            # Ctrl+L to clear messages
            messages.set([])
        elif event.name == "h" and event.ctrl:
            # Ctrl+H to toggle help
            show_help.set(not show_help())
        elif event.name == "p" and event.ctrl:
            # Ctrl+P to cycle profiles
            profiles = ["default", "plan", "accept_edits", "auto_approve", "explore"]
            current = current_profile()
            try:
                idx = (profiles.index(current) + 1) % len(profiles)
                current_profile.set(profiles[idx])
            except ValueError:
                current_profile.set(profiles[0])
        elif event.name == "q" and event.ctrl:
            # Ctrl+Q to quit
            if use_renderer:
                use_renderer().stop()
        elif event.name == "escape":
            # Escape to close help
            if show_help():
                show_help.set(False)

else:
    # Placeholders when opentui is not available
    messages = None
    current_input = None
    is_processing = None
    current_profile = None
    show_help = None
    Message = None
    _jarvis_agent = None
    _tool_registry = None
    _agent_manager = None
    _async_agent_manager = None


def run_opentui_ui(
    agent: Any,
    config: Any,
    tool_registry: Any,
    agent_manager: Any,
    async_agent_manager: Any,
    resume_session: str | None = None,
) -> None:
    """Run the OpenTUI interface."""
    global _jarvis_agent, _tool_registry, _agent_manager, _async_agent_manager
    
    # Check if opentui is available
    if not OPENTUI_AVAILABLE:
        print("ERROR: opentui is not installed.")
        print("Please install it with: pip install opentui")
        print()
        print("Note: opentui-python requires building native extensions and may need:")
        print("  - C++ build tools")
        print("  - Running: python scripts/download_opentui.py (from the source)")
        print()
        print("Alternatively, you can use the existing textual TUI with:")
        print("  python main.py        (default TUI)")
        print("  python main.py --tui  (explicit TUI)")
        return
    
    # Store references to the agent and related objects
    _jarvis_agent = agent
    _tool_registry = tool_registry
    _agent_manager = agent_manager
    _async_agent_manager = async_agent_manager
    
    # Initialize the app state
    messages.set([
        Message(
            role="assistant",
            content="🤖 Welcome to JARVIS v2.0 (OpenTUI Experimental)\n\nType your message and press Enter to start. Use Ctrl+H for help, Ctrl+Q to quit.",
            timestamp=datetime.now()
        )
    ])
    
    async def main():
        # Set up global keyboard handler
        use_keyboard(handle_keyboard)
        await render(App)
    
    asyncio.run(main())