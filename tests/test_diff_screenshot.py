import pytest
import asyncio
from textual.app import App, ComposeResult
from interface.textual_ui.widgets.tools import DiffBlock, DiffLine
from textual.widgets import Static

class TestApp(App):
    def compose(self) -> ComposeResult:
        lines = [
            DiffLine(line_number=4, content="", prefix=" "),
            DiffLine(line_number=5, content="[project]", prefix=" "),
            DiffLine(line_number=6, content="name = \"jarvis\"", prefix=" "),
            DiffLine(line_number=7, content="version = \"2.0.0\"", prefix="-"),
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
        
        with open(r"C:\Users\koula\.gemini\antigravity\brain\640aec36-8f83-44ef-bd87-1736e8bd9897\scratch\diff_dom.log", "w", encoding="utf-8") as f:
            f.write(f"Found {len(diff_lines)} diff lines\n")
            if len(diff_lines) > 0:
                line = diff_lines[0]
                f.write(f"Attributes of Static: {dir(line)}\n")
            
        # Assert that we found lines
        assert len(diff_lines) == 6
