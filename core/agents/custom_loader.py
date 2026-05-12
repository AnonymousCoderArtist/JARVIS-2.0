"""Dynamic loading of custom agents from .jarvis/agents/"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from core.agents.agent_definition import AgentDefinition

logger = logging.getLogger(__name__)


def load_custom_agent_from_py(py_file: Path) -> Any | None:
    """Load an AgentDefinition from a Python file in .jarvis/agents/

    Args:
        py_file: Path to the Python file containing the agent definition

    Returns:
        AgentDefinition if found, None otherwise
    """
    module_name = py_file.stem

    # Check if already loaded
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for {py_file}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        # Add core.agents to the module's path for imports
        module.__path__ = [str(Path(__file__).parent)]

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error loading module {module_name}: {e}")
            return None

    # Look for AgentDefinition with standard names
    # Priority: AGENT_DEFINITION > {MODULE}_DEFINITION > any *_DEFINITION
    definition = getattr(module, "AGENT_DEFINITION", None)

    if definition is None:
        definition = getattr(module, f"{module_name.upper()}_DEFINITION", None)

    if definition is None:
        # Fallback: find any attribute ending with _DEFINITION
        for attr_name in dir(module):
            if attr_name.endswith("_DEFINITION"):
                definition = getattr(module, attr_name)
                break

    # Convert dict to AgentDefinition if needed
    if isinstance(definition, dict):
        from core.agents.agent_definition import AgentDefinition
        definition = AgentDefinition(**definition)

    # Ensure dict-form definitions get their name set
    if hasattr(definition, 'name') and not definition.name:
        definition.name = module_name

    return definition


def discover_custom_agents() -> list[AgentDefinition]:
    """Discover custom agents in .jarvis/agents/ and project .jarvis/agents/

    Returns:
        List of AgentDefinition objects for discovered custom agents
    """
    definitions = []

    for base in [Path.home() / ".jarvis" / "agents", Path.cwd() / ".jarvis" / "agents"]:
        if not base.is_dir():
            continue

        for py_file in base.glob("*.py"):
            definition = load_custom_agent_from_py(py_file)
            if definition:
                definitions.append(definition)
                logger.info(f"Discovered custom agent: {definition.name}")

    return definitions


def get_custom_agent_paths() -> list[Path]:
    """Get the paths where custom agents are searched for.

    Returns:
        List of Path objects for agent directories
    """
    return [
        Path.home() / ".jarvis" / "agents",
        Path.cwd() / ".jarvis" / "agents",
    ]