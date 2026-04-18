"""Status bar widget for JARVIS TUI."""

from textual.widgets import Static


class StatusBar(Static):
    """A widget to display the status bar."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.update_status()

    def update_status(self) -> None:
        """Update the status bar text."""
        # This will be updated dynamically in the app if needed
        self.update("Provider: None | Model: None | Tools: 0")
