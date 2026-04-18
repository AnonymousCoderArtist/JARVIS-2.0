"""Banner widget for JARVIS TUI."""

from textual.widgets import Static


class Banner(Static):
    """A widget to display the banner."""

    def __init__(self):
        super().__init__()
        self.update_banner()

    def update_banner(self) -> None:
        """Update the banner text."""
        # This will be updated dynamically in the app if needed
        self.update(
            "[bold cyan]JARVIS 2.0[/bold cyan]\n[dim]The professional AI engineering assistant[/dim]"
        )