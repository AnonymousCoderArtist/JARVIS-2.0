"""Single source of truth for version management."""

__version__ = "2.0.1"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# Version schema: MAJOR.MINOR.PATCH
# - MAJOR: Breaking changes
# - MINOR: New features (backward compatible)
# - PATCH: Bug fixes