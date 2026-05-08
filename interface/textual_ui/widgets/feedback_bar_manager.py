from __future__ import annotations

import random
import time

from interface.textual_ui.agent_loop import AgentLoop
from interface.textual_ui.cli_adapters import (
    read_cache,
    write_cache,
)
from interface.textual_ui.types import Role

FEEDBACK_PROBABILITY = 0.2
FEEDBACK_COOLDOWN_SECONDS = 3600
_CACHE_SECTION = "user_feedback"
_LAST_SHOWN_KEY = "last_shown_at"
MIN_USER_MESSAGES_FOR_FEEDBACK = 3


class FeedbackBarManager:
    """Decides whether to show the feedback bar and records when feedback is given."""

    def should_show(self, agent_loop: AgentLoop) -> bool:
        if not agent_loop.telemetry_client.is_active():
            return False

        # Check if the model is a mistral model by checking the model name
        model_name = getattr(agent_loop.config, 'model', '') if agent_loop.config else ''
        if 'mistral' not in model_name.lower():
            return False

        if (
            sum(m.role == Role.user and not m.injected for m in agent_loop.messages)
            + 1  # +1 for the message the user just sent
            < MIN_USER_MESSAGES_FOR_FEEDBACK
        ):
            return False

        cache_value = read_cache(_CACHE_SECTION, _LAST_SHOWN_KEY)
        if cache_value is None:
            return False

        try:
            last_ts = int(cache_value)
        except (ValueError, TypeError):
            return False

        return (
            time.time() - last_ts >= FEEDBACK_COOLDOWN_SECONDS
            and random.random() <= FEEDBACK_PROBABILITY
        )

    def record_feedback_asked(self) -> None:
        write_cache(_CACHE_SECTION, _LAST_SHOWN_KEY, str(int(time.time())))
