"""Utility functions for tools"""

import fnmatch
import re


def wildcard_match(pattern: str, string: str) -> bool:
    """
    Match a string against a wildcard pattern

    Args:
        pattern: Pattern with wildcards (*, ?, etc.)
        string: String to match against

    Returns:
        True if string matches pattern, False otherwise
    """
    # Convert glob pattern to regex
    regex_pattern = fnmatch.translate(pattern)
    return re.match(regex_pattern, string) is not None
