"""Fork subagent utilities for parallel task execution.

This module provides utilities for spawning fork children with byte-identical
API request prefixes for prompt cache sharing.
"""

from __future__ import annotations

from .builtin_agents import FORK_AGENT

FORK_BOILERPLATE_TAG = "\n\n--- FORK_CHILD ---\n\n"
FORK_PLACEHOLDER_RESULT = "[FORK_PLACEHOLDER]"


def is_in_fork_child(messages: list[dict]) -> bool:
    """Detect if messages contain fork marker indicating a fork child.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        True if any message contains the FORK_BOILERPLATE_TAG marker
    """
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str) and FORK_BOILERPLATE_TAG in content:
            return True
    return False


def build_forked_messages(directive: str, assistant_message: dict) -> list[dict]:
    """Construct messages for fork child with shared prompt cache prefix.
    
    The goal is byte-identical API request prefixes so that multiple fork
    children can share the prompt cache.
    
    Args:
        directive: The per-child directive text to append
        assistant_message: The parent assistant message to keep in full
        
    Returns:
        List of messages suitable for fork child, including:
        - The full parent assistant message
        - User message with fork marker and identical placeholder result
        - The per-child directive text
    """
    messages = [
        assistant_message,
        {
            "role": "user",
            "content": (
                f"{FORK_BOILERPLATE_TAG}"
                f"Result: {FORK_PLACEHOLDER_RESULT}\n\n"
                f"{directive}"
            ),
        },
    ]
    return messages