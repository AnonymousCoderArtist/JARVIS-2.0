"""Utility functions for agent tools."""

from __future__ import annotations

from typing import Any


def get_agent_param(input_data: Any, *names: str) -> Any:
    """Get parameter using multiple possible names.
    
    Args:
        input_data: The input data object to get parameter from
        *names: Parameter names to try in order
        
    Returns:
        The first non-None value found for any name
    """
    for name in names:
        value = getattr(input_data, name, None)
        if value is not None:
            return value
    return None