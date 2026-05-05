from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TYPE_CHECKING

from textual.widget import Widget

from interface.textual_ui.cli_adapters import (
    HookEndEvent,
    HookEvent,
    HookRunEndEvent,
    HookRunStartEvent,
    HookStartEvent,
    ToolUIDataAdapter,
)
from interface.textual_ui.types import (
    AgentProfileChangedEvent,
    AssistantEvent,
    BaseEvent,
    CompactEndEvent,
    CompactStartEvent,
    ReasoningEvent,
    TimingEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolStreamEvent,
    UserMessageEvent,
    WaitingForInputEvent,
)
from interface.textual_ui.utils import TaggedText
from interface.textual_ui.widgets.compact import CompactMessage
from interface.textual_ui.widgets.loading import DEFAULT_LOADING_STATUS
from interface.textual_ui.widgets.messages import (
    AssistantMessage,
    HookRunContainer,
    HookSystemMessageLine,
    ReasoningMessage,
    TimingMessage,
    UserMessage,
)
from interface.textual_ui.widgets.no_markup_static import NoMarkupStatic
from interface.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage

if TYPE_CHECKING:
    from interface.textual_ui.widgets.loading import LoadingWidget

# Type aliases for callbacks
MountCallback = Callable[..., Coroutine[Any, Any, None]]
GetToolsCollapsed = Callable[[], bool]
GetThinkingCollapsed = Callable[[], bool]
OnProfileChanged = Callable[[], None]


class EventHandler:
    def __init__(
        self,
        mount_callback: MountCallback,
        get_tools_collapsed: GetToolsCollapsed,
        get_thinking_collapsed: GetThinkingCollapsed,
        on_profile_changed: OnProfileChanged | None = None,
        is_remote: bool = False,
    ) -> None:
        self.mount_callback: MountCallback = mount_callback
        self.get_tools_collapsed: GetToolsCollapsed = get_tools_collapsed
        self.get_thinking_collapsed: GetThinkingCollapsed = get_thinking_collapsed
        self.on_profile_changed: OnProfileChanged | None = on_profile_changed
        self.is_remote: bool = is_remote
        self.tool_calls: dict[str, ToolCallMessage] = {}
        self.last_tool_call: ToolCallMessage | None = None
        self.current_compact: CompactMessage | None = None
        self.current_streaming_message: AssistantMessage | None = None
        self.current_streaming_reasoning: ReasoningMessage | None = None
        self._hook_run_container: HookRunContainer | None = None

    async def _handle_hook_event(
        self, event: HookEvent, loading_widget: LoadingWidget | None = None
    ) -> None:
        if isinstance(event, HookRunStartEvent):
            self._hook_run_container = HookRunContainer()
            await self.mount_callback(self._hook_run_container)
        elif isinstance(event, HookRunEndEvent):
            if self._hook_run_container and not self._hook_run_container.display:
                await self._hook_run_container.remove()
            self._hook_run_container = None
        elif isinstance(event, HookStartEvent):
            await self.finalize_streaming()
            if loading_widget:
                loading_widget.set_status(f"Running hook {event.hook_name}")
        elif isinstance(event, HookEndEvent):
            if event.content and self._hook_run_container is not None:
                widget = HookSystemMessageLine(
                    hook_name=event.hook_name,
                    content=event.content,
                    severity=event.status,
                )
                await self._hook_run_container.add_message(widget)
            if loading_widget:
                loading_widget.set_status(DEFAULT_LOADING_STATUS)

    async def handle_event(
        self, event: BaseEvent, loading_widget: LoadingWidget | None = None
    ) -> ToolCallMessage | None:
        if isinstance(event, ReasoningEvent):
            await self._handle_reasoning_message(event)
        elif isinstance(event, AssistantEvent):
            await self._handle_assistant_message(event)
        elif isinstance(event, ToolCallEvent):
            await self.finalize_streaming()
            return await self._handle_tool_call(event, loading_widget)
        elif isinstance(event, ToolResultEvent):
            await self.finalize_streaming()
            sanitized_event = self._sanitize_event(event)
            await self._handle_tool_result(sanitized_event)
        elif isinstance(event, ToolStreamEvent):
            await self._handle_tool_stream(event)
        elif isinstance(event, CompactStartEvent):
            await self.finalize_streaming()
            await self._handle_compact_start()
        elif isinstance(event, CompactEndEvent):
            await self.finalize_streaming()
            await self._handle_compact_end(event)
        elif isinstance(event, AgentProfileChangedEvent):
            if self.on_profile_changed:
                self.on_profile_changed()
        elif isinstance(event, UserMessageEvent):
            await self.finalize_streaming()
            if self.is_remote:
                await self.mount_callback(UserMessage(event.content))
        elif isinstance(event, HookEvent):
            await self._handle_hook_event(event, loading_widget)
        elif isinstance(event, WaitingForInputEvent):
            await self.finalize_streaming()
        elif isinstance(event, TimingEvent):
            await self._handle_timing_event(event)
        else:
            await self.finalize_streaming()
            await self._handle_unknown_event(event)
        return None

    async def _handle_timing_event(self, event: TimingEvent) -> None:
        """Handle timing event with target design."""
        timing_msg = TimingMessage(event.duration)
        await self.mount_callback(timing_msg)

    def _sanitize_event(self, event: ToolResultEvent) -> ToolResultEvent:
        return ToolResultEvent(
            tool_name=event.tool_name,
            tool_class=event.tool_class,
            result=event.result,
            error=str(TaggedText.from_string(event.error).message)
            if event.error
            else "",
            skipped=event.skipped,
            skip_reason=str(TaggedText.from_string(event.skip_reason).message)
            if event.skip_reason
            else "",
            cancelled=event.cancelled,
            duration=event.duration,
            tool_call_id=event.tool_call_id,
        )

    async def _handle_tool_call(
        self, event: ToolCallEvent, loading_widget: LoadingWidget | None = None
    ) -> ToolCallMessage | None:
        tool_call_id = event.tool_call_id
        existing_tool_call = self.tool_calls.get(tool_call_id) if tool_call_id else None
        if existing_tool_call:
            existing_tool_call.update_event(event)
            tool_call = existing_tool_call
        else:
            tool_call = ToolCallMessage(event)
            if tool_call_id:
                self.tool_calls[tool_call_id] = tool_call
            self.last_tool_call = tool_call
            await self.mount_callback(tool_call)

        if loading_widget and event.tool_class:
            adapter = ToolUIDataAdapter(event.tool_class)
            loading_widget.set_status(adapter.get_status_text())

        return tool_call

    async def _handle_tool_result(self, event: ToolResultEvent) -> None:
        tools_collapsed = self.get_tools_collapsed()

        call_widget = (
            self.tool_calls.get(event.tool_call_id) if event.tool_call_id else None
        )
        
        # Fallback to last tool call if ID is missing or mismatched
        if not call_widget:
            call_widget = self.last_tool_call

        tool_result = ToolResultMessage(event, call_widget, collapsed=tools_collapsed)
        await self.mount_callback(tool_result, after=call_widget)

    async def _handle_tool_stream(self, event: ToolStreamEvent) -> None:
        tool_call = self.tool_calls.get(event.tool_call_id)
        if tool_call:
            tool_call.set_stream_message(event.content)

    async def _handle_assistant_message(self, event: AssistantEvent) -> None:
        if self.current_streaming_reasoning is not None:
            self.current_streaming_reasoning.stop_spinning()
            await self.current_streaming_reasoning.stop_stream()
            self.current_streaming_reasoning = None

        if self.current_streaming_message is None:
            msg = AssistantMessage(event.content, enable_math=False)
            # Apply heartbeat styling if this is a heartbeat message
            if event.is_heartbeat:
                msg.add_class("heartbeat-message")
            self.current_streaming_message = msg
            await self.mount_callback(msg)
        else:
            await self.current_streaming_message.append_content(event.content)

    async def _handle_reasoning_message(self, event: ReasoningEvent) -> None:
        if self.current_streaming_message is not None:
            await self.current_streaming_message.stop_stream()
            if self.current_streaming_message.is_stripped_content_empty():
                await self.current_streaming_message.remove()
            self.current_streaming_message = None

        if self.current_streaming_reasoning is None:
            thinking_collapsed = self.get_thinking_collapsed()
            msg = ReasoningMessage(event.content, collapsed=thinking_collapsed)
            self.current_streaming_reasoning = msg
            await self.mount_callback(msg)
        else:
            await self.current_streaming_reasoning.append_content(event.content)

    async def _handle_compact_start(self) -> None:
        compact_msg = CompactMessage()
        self.current_compact = compact_msg
        await self.mount_callback(compact_msg)

    async def _handle_compact_end(self, event: CompactEndEvent) -> None:
        if self.current_compact:
            # Need to get context tokens from event, assuming they exist
            old_tokens = getattr(event, 'old_context_tokens', 0)
            new_tokens = getattr(event, 'new_context_tokens', 0)
            self.current_compact.set_complete(
                old_tokens=old_tokens, new_tokens=new_tokens
            )
            self.current_compact = None

    async def _handle_unknown_event(self, event: BaseEvent) -> None:
        await self.mount_callback(NoMarkupStatic(str(event), classes="unknown-event"))

    async def finalize_streaming(self) -> None:
        if self.current_streaming_reasoning is not None:
            self.current_streaming_reasoning.stop_spinning()
            await self.current_streaming_reasoning.stop_stream()
            self.current_streaming_reasoning = None
        if self.current_streaming_message is not None:
            await self.current_streaming_message.stop_stream()
            self.current_streaming_message = None

    def stop_current_tool_call(self, success: bool = True) -> None:
        for tool_call in self.tool_calls.values():
            tool_call.stop_spinning(success=success)
        self.tool_calls.clear()

    def stop_current_compact(self) -> None:
        if self.current_compact:
            self.current_compact.stop_spinning(success=False)
            self.current_compact = None
