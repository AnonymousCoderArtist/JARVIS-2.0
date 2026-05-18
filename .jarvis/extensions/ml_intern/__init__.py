"""ML Intern — Autonomous ML engineering agent for JARVIS.

Ported from huggingface/ml-intern as a JARVIS extension.

This extension registers the ``ml-intern`` SUBAGENT with its own system prompt
and a full set of ML-focused tools for the Hugging Face ecosystem:

- hf_papers: Paper discovery, citations, and reading
- explore_hf_docs / fetch_hf_docs / find_hf_api: HF documentation & API search
- hf_inspect_dataset: Dataset analysis and validation
- github_find_examples / github_list_repos / github_read_file: GitHub research
- hf_repo_files / hf_repo_git: HF repo management
- web_search: DuckDuckGo web search
- research: Sub-agent for literature review
- plan_tool: Todo list tracking
- hf_jobs: HF Training Jobs management
- notify: Out-of-band notifications
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jarvis.api import AgentDefinition, AgentType, ExtensionAPI

if TYPE_CHECKING:
    from .papers_tool import HfPapersTool  # type: ignore
    from .docs_tools import ExploreHfDocsTool, FetchHfDocsTool, FindHfApiTool  # type: ignore
    from .dataset_tools import HfInspectDatasetTool  # type: ignore
    from .github_find_examples import GithubFindExamplesTool  # type: ignore
    from .github_list_repos import GithubListReposTool  # type: ignore
    from .github_read_file import GithubReadFileTool  # type: ignore
    from .hf_repo_files_tool import HfRepoFilesTool  # type: ignore
    from .hf_repo_git_tool import HfRepoGitTool  # type: ignore
    from .web_search_tool import WebSearchTool  # type: ignore
    from .research_tool import ResearchTool  # type: ignore
    from .plan_tool import PlanTool  # type: ignore
    from .jobs_tool import HfJobsTool  # type: ignore
    from .notify_tool import NotifyTool  # type: ignore
    from .system_prompt import get_system_prompt  # type: ignore

logger = logging.getLogger(__name__)

__version__ = "0.1.0"
__description__ = "Autonomous ML engineering agent (ported from huggingface/ml-intern)"
__author__ = "Hugging Face (port by JARVIS)"


async def jarvis(api: ExtensionAPI) -> None:
    """Register the ml-intern agent and all its tools."""

    # ── Import tools (lazy to avoid import errors if deps missing) ──
    tools = []

    try:
        from .papers_tool import HfPapersTool  # type: ignore
        tools.append(HfPapersTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load HfPapersTool: %s", e)

    try:
        from .docs_tools import ExploreHfDocsTool, FetchHfDocsTool, FindHfApiTool  # type: ignore
        tools.append(ExploreHfDocsTool())
        tools.append(FetchHfDocsTool())
        tools.append(FindHfApiTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load docs tools: %s", e)

    try:
        from .dataset_tools import HfInspectDatasetTool  # type: ignore
        tools.append(HfInspectDatasetTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load HfInspectDatasetTool: %s", e)

    try:
        from .github_find_examples import GithubFindExamplesTool  # type: ignore
        from .github_list_repos import GithubListReposTool  # type: ignore
        from .github_read_file import GithubReadFileTool  # type: ignore
        tools.append(GithubFindExamplesTool())
        tools.append(GithubListReposTool())
        tools.append(GithubReadFileTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load github tools: %s", e)

    try:
        from .hf_repo_files_tool import HfRepoFilesTool  # type: ignore
        from .hf_repo_git_tool import HfRepoGitTool  # type: ignore
        tools.append(HfRepoFilesTool())
        tools.append(HfRepoGitTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load hf_repo tools: %s", e)

    try:
        from .web_search_tool import WebSearchTool  # type: ignore
        tools.append(WebSearchTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load WebSearchTool: %s", e)

    try:
        from .research_tool import ResearchTool  # type: ignore
        tools.append(ResearchTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load ResearchTool: %s", e)

    try:
        from .plan_tool import PlanTool  # type: ignore
        tools.append(PlanTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load PlanTool: %s", e)

    try:
        from .jobs_tool import HfJobsTool  # type: ignore
        tools.append(HfJobsTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load HfJobsTool: %s", e)

    try:
        from .notify_tool import NotifyTool  # type: ignore
        tools.append(NotifyTool())
    except Exception as e:
        logger.warning("ml-intern: failed to load NotifyTool: %s", e)

    # ── System prompt ──
    try:
        from .system_prompt import get_system_prompt  # type: ignore
    except Exception as e:
        logger.warning("ml-intern: failed to load system prompt: %s", e)
        def get_system_prompt(num_tools=None):
            return "You are ML Intern, an autonomous ML engineering assistant."

    # ── Register tools (agent-local: only available to the ml-intern subagent) ──
    for tool in tools:
        api.agent_tools(tool)

    # ── Register agent ──
    num_tools = len(tools)

    def _get_prompt() -> str:
        return get_system_prompt(num_tools=num_tools)

    api.agents(AgentDefinition(
        name="ml-intern",
        description=(
            "Autonomous ML engineering agent for the Hugging Face ecosystem. "
            "Use for: ML research (papers, citations, datasets), training jobs, "
            "HF documentation lookup, GitHub code research, and HF repo management. "
            "Specialized for ML/AI workflows with deep HF ecosystem integration."
        ),
        tools=[t.name for t in tools],
        model="inherit",
        agent_type=AgentType.AGENT,
        max_turns=200,
        system_prompt=_get_prompt,
    ))

    logger.info("ml-intern extension loaded: %d tools registered", num_tools)
