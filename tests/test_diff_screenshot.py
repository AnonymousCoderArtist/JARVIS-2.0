
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from jarvis.interface.textual_ui.widgets.tools import DiffBlock, DiffLine


class TestApp(App):
    def compose(self) -> ComposeResult:
        lines = [
            DiffLine(line_number=4, content="", prefix=" "),
            DiffLine(line_number=5, content="[project]", prefix=" "),
            DiffLine(line_number=6, content="name = \"jarvis\"", prefix=" "),
            DiffLine(line_number=7, content="version = \"2.1.0\"", prefix="-"),
            DiffLine(line_number=7, content="version = \"2.0.1\"", prefix="+"),
            DiffLine(line_number=8, content="description = \"...\"", prefix=" "),
        ]
        yield DiffBlock(lines)

@pytest.mark.asyncio
async def test_diff_dom():
    app = TestApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        # Find all Static widgets with class diff-line
        diff_lines = pilot.app.query(Static).filter(".diff-line")

        import tempfile, os
        log_path = os.path.join(tempfile.gettempdir(), "diff_dom.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Found {len(diff_lines)} diff lines\n")
            if len(diff_lines) > 0:
                line = diff_lines[0]
                f.write(f"Attributes of Static: {dir(line)}\n")

        # Assert that we found lines
        assert len(diff_lines) == 6
