"""Research sub-agent tool — spawns a cheap LLM call for literature review.

Ported from huggingface/ml-intern agent/tools/research_tool.py.

NOTE: In the JARVIS extension context, this tool delegates to the JARVIS
agent system rather than directly calling litellm. The tool description
and system prompt are preserved so the ml-intern agent knows when to use it.
"""

from __future__ import annotations

import logging

from jarvis.api import BaseTool, ToolInput, ToolOutput

logger = logging.getLogger(__name__)

# Tools the research agent can use (read-only subset)
RESEARCH_TOOL_NAMES = {
    "read", "bash", "explore_hf_docs", "fetch_hf_docs", "find_hf_api",
    "hf_papers", "github_find_examples", "github_list_repos", "github_read_file",
    "web_search", "hf_inspect_dataset", "hf_repo_files",
}

RESEARCH_SYSTEM_PROMPT = """\
You are a research sub-agent for an ML engineering assistant.
Your primary job: mine the literature to find the best training recipes —
then back them up with working code and up to date documentation. The main agent will use
your findings to implement the actual solution.

# Start from the literature

Your default approach is a deep literature crawl. Do not start from docs or
example scripts — start from papers. Papers contain the results, and results
tell you what actually works.

## The crawl

1. **Find anchor papers**: Search for the task/domain. Identify the landmark paper(s).
2. **Crawl the citation graph**: Use `citation_graph` on the anchor paper(s). Look DOWNSTREAM.
3. **Read methodology sections**: Read sections 3, 4, 5 (Methodology, Experiments, Results).
4. **Attribute results to recipes**: Link RESULT to RECIPE that produced it.
5. **Validate datasets**: Check if they exist on HF Hub with `hf_inspect_dataset`.
6. **Find code**: Find working implementation code via `github_find_examples` and `github_read_file`.

# Output format

Your output MUST be structured as a ranked list of training recipes, each attributed to published results:

## Recipe table (REQUIRED)
For each promising approach found, report:
- **Paper**: title, arxiv_id, date, venue
- **Result**: exact benchmark scores
- **Dataset(s)**: name, size, source, HF Hub availability, format verified
- **Method**: training approach, key hyperparameters
- **What made it work**: the specific insight or trick

Rank recipes by result quality.

## Code patterns
- Key imports, configurations, and usage patterns from working examples

## Recommendations
- Which recipe to implement first and why
- What datasets to use (with HF Hub paths, verified)

Be concise. Your output goes into another agent's context — every token counts.
Aim for 500-1500 words max.
"""


class ResearchTool(BaseTool):
    name = "research"
    description = (
        "Spawn a research sub-agent to explore documentation, codebases, "
        "or repos WITHOUT polluting the main conversation context. "
        "The sub-agent gets its own independent context window with read-only "
        "research tools and returns a concise summary of findings.\n\n"
        "Use this for:\n"
        "- Researching current API usage before implementing ML tasks\n"
        "- Exploring HF docs, reading papers, analyzing GitHub repos\n"
        "- Any research where raw tool outputs would be too verbose\n\n"
        "The sub-agent knows how to use github_find_examples, github_read_file, "
        "explore_hf_docs, fetch_hf_docs, hf_inspect_dataset, hf_papers, etc. "
        "Just describe what you need researched."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "Detailed description of what to research. Be specific: "
                    "include library names, trainer types, dataset names, "
                    "repo names, or doc pages to explore."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional context from the current conversation that the "
                    "research agent needs."
                ),
            },
        },
        "required": ["task"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        task = input_data.query or ""
        context = getattr(input_data, "context", "")

        if not task:
            return ToolOutput(success=False, result=None, error="No research task provided.")

        # In the JARVIS extension context, we construct the research prompt
        # and return it as a structured request. The JARVIS agent system will
        # handle the actual sub-agent invocation.
        user_content = f"Research task: {task}"
        if context:
            user_content = f"Context: {context}\n\n{user_content}"

        # Build a structured research request that the agent can act on
        result = (
            f"## Research Request\n\n"
            f"**Task:** {task}\n"
        )
        if context:
            result += f"**Context:** {context}\n"
        result += (
            f"\n**Instructions:** {RESEARCH_SYSTEM_PROMPT[:500]}...\n\n"
            f"Use the following tools to complete this research:\n"
            f"- hf_papers: Search and read papers\n"
            f"- explore_hf_docs + fetch_hf_docs: Browse HF documentation\n"
            f"- hf_inspect_dataset: Validate dataset formats\n"
            f"- github_find_examples + github_read_file: Find and study working code\n"
            f"- web_search: Search the web for current information\n"
        )

        return ToolOutput(success=True, result=result)
