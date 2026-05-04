"""Notification tool — Windows toast notifications."""

from typing import Annotated, Any

from pydantic import Field

from core.windows.analytics import with_analytics


def create_notification_tool(desktop, analytics=None):
    """Create a notification tool."""
    @with_analytics(analytics, "Notification-Tool")
    def notification_tool(
        title: Annotated[
            str,
            Field(description="The title/heading of the toast notification."),
        ],
        message: Annotated[
            str,
            Field(description="The body text of the toast notification displayed below the title."),
        ],
        app_id: Annotated[
            str,
            Field(
                description="The valid Application User Model ID of the toast notification. Required to display the notification in a specific app.",
            ),
        ],
    ) -> str:
        try:
            return desktop.send_notification(title, message, app_id)
        except Exception as e:
            return f"Error sending notification: {str(e)}"
    
    return notification_tool