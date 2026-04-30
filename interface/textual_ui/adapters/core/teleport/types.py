"""Teleport types."""

from dataclasses import dataclass


@dataclass
class TeleportAuthCompleteEvent:
    """Teleport auth complete event."""
    pass


@dataclass
class TeleportAuthRequiredEvent:
    """Teleport auth required event."""
    pass


@dataclass
class TeleportCheckingGitEvent:
    """Teleport checking git event."""
    pass


@dataclass
class TeleportCompleteEvent:
    """Teleport complete event."""
    pass


@dataclass
class TeleportFetchingUrlEvent:
    """Teleport fetching URL event."""
    pass


@dataclass
class TeleportPushingEvent:
    """Teleport pushing event."""
    pass


@dataclass
class TeleportPushRequiredEvent:
    """Teleport push required event."""
    pass


@dataclass
class TeleportPushResponseEvent:
    """Teleport push response event."""
    pass


@dataclass
class TeleportStartingWorkflowEvent:
    """Teleport starting workflow event."""
    pass


@dataclass
class TeleportWaitingForGitHubEvent:
    """Teleport waiting for GitHub event."""
    pass
