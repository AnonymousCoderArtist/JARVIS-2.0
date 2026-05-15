"""Tests for the rewind feature: RewindManager logic and RewindApp widget."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from core.rewind.manager import Checkpoint, FileSnapshot, RewindError, RewindManager
from interface.textual_ui.widgets.rewind_app import RewindApp


# ---------------------------------------------------------------------------
# RewindManager – message format handling
# ---------------------------------------------------------------------------


class TestRewindManagerMessageFormats:
    """Verify get_rewindable_messages supports both role-based and agent-memory formats."""

    def _make_manager(self, messages, *, save_called=None, reset_called=None):
        if save_called is None:
            save_called = []
        if reset_called is None:
            reset_called = []

        async def save():
            save_called.append(True)

        def reset():
            reset_called.append(True)

        return RewindManager(messages, save, reset)

    def test_standard_user_role_messages(self):
        """Messages with role='user' are returned as rewindable."""
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "how are you"},
        ]
        mgr = self._make_manager(msgs)
        result = mgr.get_rewindable_messages()
        assert result == [(0, "hello"), (2, "how are you")]

    def test_non_user_role_skipped(self):
        """Messages without role='user' are not returned."""
        msgs = [
            {"role": "assistant", "content": "hi"},
            {"role": "tool", "content": "result", "tool_call_id": "call_1"},
        ]
        mgr = self._make_manager(msgs)
        result = mgr.get_rewindable_messages()
        assert result == []

    def test_mixed_messages(self):
        """Only role='user' entries are returned."""
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "tool", "content": "result"},
        ]
        mgr = self._make_manager(msgs)
        result = mgr.get_rewindable_messages()
        assert result == [(0, "hi")]

    def test_empty_messages_list(self):
        mgr = self._make_manager([])
        assert mgr.get_rewindable_messages() == []

    def test_assistant_only_messages_skipped(self):
        """Messages with role=assistant should be excluded."""
        msgs = [
            {"role": "assistant", "content": "hi"},
        ]
        mgr = self._make_manager(msgs)
        assert mgr.get_rewindable_messages() == []

    def test_empty_content_skipped(self):
        """Messages with empty content should be skipped."""
        msgs = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "real"},
        ]
        mgr = self._make_manager(msgs)
        assert mgr.get_rewindable_messages() == [(1, "real")]


# ---------------------------------------------------------------------------
# RewindManager – rewind_to_message
# ---------------------------------------------------------------------------


class TestRewindToMessage:
    def _make_manager(self, messages, *, save_called=None, reset_called=None):
        if save_called is None:
            save_called = []
        if reset_called is None:
            reset_called = []

        async def save():
            save_called.append(True)

        def reset():
            reset_called.append(True)

        return RewindManager(messages, save, reset)

    @pytest.mark.asyncio
    async def test_rewind_standard_format(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
            {"role": "assistant", "content": "see ya"},
        ]
        save_called = []
        reset_called = []
        mgr = self._make_manager(msgs, save_called=save_called, reset_called=reset_called)

        content, errors = await mgr.rewind_to_message(0, restore_files=False)

        assert content == "hello"
        assert errors == []
        assert save_called == [True]
        assert reset_called == [True]
        assert len(msgs) == 0  # truncated to before index 0

    @pytest.mark.asyncio
    async def test_rewind_agent_memory_format(self):
        msgs = [
            {"role": "user", "content": "do stuff"},
            {"role": "user", "content": "more stuff"},
        ]
        save_called = []
        reset_called = []
        mgr = self._make_manager(msgs, save_called=save_called, reset_called=reset_called)

        content, errors = await mgr.rewind_to_message(1, restore_files=False)

        assert content == "more stuff"
        assert len(msgs) == 1  # truncated to before index 1

    @pytest.mark.asyncio
    async def test_rewind_no_task_prefix_unchanged(self):
        msgs = [
            {"role": "user", "content": "plain message"},
        ]
        mgr = self._make_manager(msgs)
        content, _ = await mgr.rewind_to_message(0, restore_files=False)
        assert content == "plain message"

    @pytest.mark.asyncio
    async def test_rewind_invalid_index_raises(self):
        msgs = [
            {"role": "user", "content": "hi"},
        ]
        mgr = self._make_manager(msgs)
        with pytest.raises(RewindError):
            await mgr.rewind_to_message(5, restore_files=False)

    @pytest.mark.asyncio
    async def test_rewind_negative_index_raises(self):
        mgr = self._make_manager([{"role": "user", "content": "hi"}])
        with pytest.raises(RewindError):
            await mgr.rewind_to_message(-1, restore_files=False)

    @pytest.mark.asyncio
    async def test_rewind_non_user_message_raises(self):
        msgs = [
            {"role": "assistant", "content": "hi"},
        ]
        mgr = self._make_manager(msgs)
        with pytest.raises(RewindError):
            await mgr.rewind_to_message(0, restore_files=False)

    @pytest.mark.asyncio
    async def test_rewind_mid_conversation(self):
        msgs = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "third"},
        ]
        mgr = self._make_manager(msgs)
        content, _ = await mgr.rewind_to_message(2, restore_files=False)
        assert content == "second"
        assert len(msgs) == 2  # first + a1


# ---------------------------------------------------------------------------
# RewindManager – checkpoint and file snapshots
# ---------------------------------------------------------------------------


class TestRewindCheckpoints:
    def _make_manager(self, messages):
        async def save():
            pass

        return RewindManager(messages, save, lambda: None)

    def test_create_checkpoint(self):
        msgs = [{"role": "user", "content": "hi"}]
        mgr = self._make_manager(msgs)
        mgr.create_checkpoint()
        assert len(mgr.checkpoints) == 1
        assert mgr.checkpoints[0].message_index == 1  # len(msgs) at creation time

    def test_add_snapshot(self):
        msgs = [{"role": "user", "content": "hi"}]
        mgr = self._make_manager(msgs)
        mgr.create_checkpoint()
        snap = FileSnapshot(path="/tmp/test.py", content=b"print('hello')")
        mgr.add_snapshot(snap)
        assert mgr.checkpoints[0].files[0].path == "/tmp/test.py"

    def test_add_snapshot_dedup(self):
        msgs = [{"role": "user", "content": "hi"}]
        mgr = self._make_manager(msgs)
        mgr.create_checkpoint()
        snap1 = FileSnapshot(path="/tmp/test.py", content=b"v1")
        snap2 = FileSnapshot(path="/tmp/test.py", content=b"v2")
        mgr.add_snapshot(snap1)
        mgr.add_snapshot(snap2)
        # Should not duplicate – same path, only first kept
        assert len(mgr.checkpoints[0].files) == 1

    @pytest.mark.asyncio
    async def test_rewind_with_file_restore(self, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("original content")

        msgs = [{"role": "user", "content": "hi"}]
        mgr = self._make_manager(msgs)
        # Create checkpoint BEFORE the user message (index 0)
        # Checkpoint message_index = len(msgs) = 1 at creation time,
        # but we need it at index 0 for rewind_to_message to find it.
        # So we create the checkpoint when msgs is empty.
        mgr2 = self._make_manager([])
        mgr2.create_checkpoint()  # checkpoint at index 0
        mgr2.add_snapshot(FileSnapshot(path=str(file_path), content=b"original content"))
        msgs2 = [{"role": "user", "content": "hi"}]
        mgr2._messages = msgs2
        mgr2._checkpoints[0].message_index = 0

        # Simulate file being modified
        file_path.write_text("modified content")

        # Rewind with file restore
        content, errors = await mgr2.rewind_to_message(0, restore_files=True)
        assert content == "hi"
        # File should be restored to original
        assert file_path.read_text() == "original content"

    @pytest.mark.asyncio
    async def test_rewind_file_restore_deletes_new_file(self, tmp_path):
        file_path = tmp_path / "new_file.py"

        mgr = self._make_manager([])
        mgr.create_checkpoint()  # checkpoint at index 0
        # File doesn't exist at checkpoint time
        mgr.add_snapshot(FileSnapshot(path=str(file_path), content=None))
        mgr._messages = [{"role": "user", "content": "hi"}]
        mgr._checkpoints[0].message_index = 0

        # File now exists
        file_path.write_text("newly created")
        assert file_path.exists()

        await mgr.rewind_to_message(0, restore_files=True)
        assert not file_path.exists()

    def test_has_file_changes_at(self, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("v1")

        mgr = self._make_manager([])
        mgr.create_checkpoint()  # checkpoint at index 0
        mgr.add_snapshot(FileSnapshot(path=str(file_path), content=b"v1"))
        mgr._messages = [{"role": "user", "content": "hi"}]
        mgr._checkpoints[0].message_index = 0

        assert mgr.has_file_changes_at(0) is False

        # Modify the file
        file_path.write_text("v2")
        assert mgr.has_file_changes_at(0) is True

    def test_has_file_changes_at_no_checkpoint(self):
        mgr = self._make_manager([{"role": "user", "content": "hi"}])
        assert mgr.has_file_changes_at(0) is False


# ---------------------------------------------------------------------------
# RewindApp – widget tests (need an App wrapper for run_test)
# ---------------------------------------------------------------------------


class _RewindTestApp(App):
    """Minimal app that mounts a RewindApp for testing."""

    CSS = """
    RewindApp { height: auto; }
    """

    def __init__(self, message_preview: str, has_file_changes: bool) -> None:
        super().__init__()
        self._message_preview = message_preview
        self._has_file_changes = has_file_changes
        self.posted_messages: list[str] = []

    def compose(self) -> ComposeResult:
        yield RewindApp(
            message_preview=self._message_preview,
            has_file_changes=self._has_file_changes,
        )

    def on_rewind_app_rewind_with_restore(self, event: RewindApp.RewindWithRestore) -> None:
        self.posted_messages.append("RewindWithRestore")
        event.stop()

    def on_rewind_app_rewind_without_restore(self, event: RewindApp.RewindWithoutRestore) -> None:
        self.posted_messages.append("RewindWithoutRestore")
        event.stop()

    def on_rewind_app_rewind_cancelled(self, event: RewindApp.RewindCancelled) -> None:
        self.posted_messages.append("RewindCancelled")
        event.stop()


class TestRewindAppWidget:
    @pytest.mark.asyncio
    async def test_rewind_app_shows_file_restore_option_when_changes(self):
        app = _RewindTestApp("test message", has_file_changes=True)
        async with app.run_test() as pilot:
            rewind = app.query_one(RewindApp)
            assert rewind._option_count() == 2
            assert rewind._options[0][1].value == "edit_and_restore"
            assert rewind._options[1][1].value == "edit_only"

    @pytest.mark.asyncio
    async def test_rewind_app_shows_edit_only_when_no_file_changes(self):
        app = _RewindTestApp("test message", has_file_changes=False)
        async with app.run_test() as pilot:
            rewind = app.query_one(RewindApp)
            assert rewind._option_count() == 1
            assert rewind._options[0][1].value == "edit_only"

    @pytest.mark.asyncio
    async def test_rewind_app_arrow_navigation(self):
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            rewind = app.query_one(RewindApp)
            assert rewind.selected_option == 0
            await pilot.press("down")
            assert rewind.selected_option == 1
            await pilot.press("down")
            assert rewind.selected_option == 0  # wraps around
            await pilot.press("up")
            assert rewind.selected_option == 1  # wraps around

    @pytest.mark.asyncio
    async def test_rewind_app_select_posts_rewind_with_restore(self):
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            # Option 0 is edit+restore when has_file_changes – press enter
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert "RewindWithRestore" in app.posted_messages

    @pytest.mark.asyncio
    async def test_rewind_app_select_edit_only_posts_without_restore(self):
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            # Select option 1 (edit-only)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert "RewindWithoutRestore" in app.posted_messages

    @pytest.mark.asyncio
    async def test_rewind_app_escape_cancels(self):
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            await pilot.press("escape")
            await pilot.pause(0.3)
            assert "RewindCancelled" in app.posted_messages

    @pytest.mark.asyncio
    async def test_rewind_app_number_key_selects_option(self):
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            await pilot.press("2")
            await pilot.pause(0.3)
            assert "RewindWithoutRestore" in app.posted_messages

    @pytest.mark.asyncio
    async def test_rewind_app_update_preview(self):
        app = _RewindTestApp("old preview", has_file_changes=False)
        async with app.run_test() as pilot:
            rewind = app.query_one(RewindApp)
            rewind.update_preview("new preview text")
            assert rewind._message_preview == "new preview text"

    @pytest.mark.asyncio
    async def test_rewind_app_jk_navigation(self):
        """j/k keys should navigate options (vim-style)."""
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            rewind = app.query_one(RewindApp)
            assert rewind.selected_option == 0
            await pilot.press("j")
            assert rewind.selected_option == 1
            await pilot.press("k")
            assert rewind.selected_option == 0

    @pytest.mark.asyncio
    async def test_rewind_app_has_message_navigation_bindings(self):
        """RewindApp should have alt+up/down and ctrl+p/n bindings for message navigation."""
        app = _RewindTestApp("test", has_file_changes=True)
        async with app.run_test() as pilot:
            rewind = app.query_one(RewindApp)
            binding_keys = {b.key for b in rewind.BINDINGS}
            assert "alt+up" in binding_keys
            assert "alt+down" in binding_keys
            assert "ctrl+p" in binding_keys
            assert "ctrl+n" in binding_keys


# ---------------------------------------------------------------------------
# RewindManager – on_messages_reset
# ---------------------------------------------------------------------------


class TestRewindManagerMessagesReset:
    def test_on_messages_reset_clears_checkpoints(self):
        """on_messages_reset should clear checkpoints when not rewinding."""
        msgs = [{"role": "user", "content": "hi"}]
        mgr = RewindManager(msgs, lambda: None, lambda: None)  # type: ignore
        mgr.create_checkpoint()
        mgr.add_snapshot(FileSnapshot(path="/tmp/test.py", content=b"v1"))
        assert len(mgr.checkpoints) == 1

        mgr.on_messages_reset()
        assert len(mgr.checkpoints) == 0

    def test_on_messages_reset_preserves_checkpoints_during_rewind(self):
        """on_messages_reset should NOT clear checkpoints during active rewind."""
        msgs = [{"role": "user", "content": "hi"}]
        mgr = RewindManager(msgs, lambda: None, lambda: None)  # type: ignore
        mgr.create_checkpoint()
        assert len(mgr.checkpoints) == 1

        mgr._is_rewinding = True
        mgr.on_messages_reset()
        assert len(mgr.checkpoints) == 1  # preserved during rewind


# ---------------------------------------------------------------------------
# AgentLoop – file tracking tools
# ---------------------------------------------------------------------------


class TestAgentLoopFileTracking:
    def test_file_modifying_tools_set_defined(self):
        """AgentLoop should define sets of file-modifying and shell tools."""
        from interface.textual_ui.agent_loop import AgentLoop
        assert "write" in AgentLoop.FILE_MODIFYING_TOOLS
        assert "edit" in AgentLoop.FILE_MODIFYING_TOOLS
        assert "bash" in AgentLoop.SHELL_TOOLS
