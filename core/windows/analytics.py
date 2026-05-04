"""Analytics for Windows automation module.

Persists user ID and session data in ~/.jarvis/windows.
"""

from typing import Dict, Any, TypeVar, Callable, Protocol, Awaitable
import uuid
from functools import wraps
from pathlib import Path
import logging
import time
import os

from core.windows.paths import WINDOWS_DATA_DIR, USER_ID_FILE

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

T = TypeVar("T")


class Analytics(Protocol):
    async def track_tool(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Tracks the execution of a tool."""
        ...

    async def track_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Tracks an error that occurred during the execution of a tool."""
        ...

    async def is_feature_enabled(self, feature: str) -> bool:
        """Checks if a feature flag is enabled."""
        ...

    async def close(self) -> None:
        """Closes the analytics client."""
        ...


class PostHogAnalytics:
    """Analytics client for Windows automation.
    
    Saves user ID to ~/.jarvis/windows for persistence across sessions.
    """
    API_KEY = "phc_uxdCItyVTjXNU0sMPr97dq3tcz39scQNt3qjTYw5vLV"
    HOST = "https://us.i.posthog.com"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and os.getenv("ANONYMIZED_TELEMETRY", "true").lower() != "false"
        self.client = None
        self._user_id = None
        self.mcp_interaction_id = f"jarvis_{int(time.time() * 1000)}_{os.getpid()}"
        
        if self.enabled:
            try:
                import posthog
                self.client = posthog.Posthog(
                    self.API_KEY,
                    host=self.HOST,
                    disable_geoip=False,
                    enable_exception_autocapture=True,
                    debug=False,
                )
                logger.debug(f"Initialized analytics with session ID: {self.mcp_interaction_id}")
            except ImportError:
                logger.debug("PostHog not available, analytics disabled")
                self.enabled = False

    @property
    def user_id(self) -> str:
        if self._user_id:
            return self._user_id

        if USER_ID_FILE.exists():
            self._user_id = USER_ID_FILE.read_text(encoding="utf-8").strip()
        else:
            self._user_id = str(uuid.uuid4())
            try:
                USER_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
                USER_ID_FILE.write_text(self._user_id, encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not persist user ID: {e}")

        return self._user_id

    async def track_tool(self, tool_name: str, result: Dict[str, Any]) -> None:
        if not self.enabled or not self.client:
            return
            
        self.client.capture(
            distinct_id=self.user_id,
            event="tool_executed",
            properties={
                "tool_name": tool_name,
                "session_id": self.mcp_interaction_id,
                **result,
            },
        )

        duration = result.get("duration_ms", 0)
        success_mark = "SUCCESS" if result.get("success") else "FAILED"
        print(f"[Analytics] {tool_name}: {success_mark} ({duration}ms)")
        logger.info(f"{tool_name}: {success_mark} ({duration}ms)")

    async def track_error(self, error: Exception, context: Dict[str, Any]) -> None:
        if not self.enabled or not self.client:
            return
            
        self.client.capture(
            distinct_id=self.user_id,
            event="exception",
            properties={
                "exception": str(error),
                "traceback": str(error) if not hasattr(error, "__traceback__") else str(error),
                "session_id": self.mcp_interaction_id,
                **context,
            },
        )

        logger.error(f"ERROR in {context.get('tool_name')}: {error}")

    async def is_feature_enabled(self, feature: str) -> bool:
        if not self.enabled or not self.client:
            return False
        return self.client.is_feature_enabled(feature, self.user_id)

    async def close(self) -> None:
        if self.enabled and self.client:
            self.client.shutdown()
            logger.debug("Closed analytics")


def with_analytics(analytics_instance: Analytics | None, tool_name: str):
    """
    Decorator to wrap tool functions with analytics tracking.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            start = time.time()

            client_data = {}
            try:
                # Extract client info if available
                for arg in args:
                    if hasattr(arg, 'session') and arg.session:
                        client_data["client_name"] = "jarvis"
                        break
            except Exception:
                pass

            try:
                if hasattr(func, '__call__'):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                duration_ms = int((time.time() - start) * 1000)

                if analytics_instance:
                    await analytics_instance.track_tool(
                        tool_name,
                        {"duration_ms": duration_ms, "success": True, **client_data},
                    )

                return result
            except Exception as error:
                duration_ms = int((time.time() - start) * 1000)
                if analytics_instance:
                    await analytics_instance.track_error(
                        error,
                        {
                            "tool_name": tool_name,
                            "duration_ms": duration_ms,
                            **client_data,
                        },
                    )
                raise error

        return wrapper

    return decorator