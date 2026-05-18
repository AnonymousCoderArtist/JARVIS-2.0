"""GitHub Find Examples Tool - Discover examples, tutorials, and guides for any library

Lists all files in a repository and performs deterministic keyword search.
"""

import os
from typing import Any, Dict, List

import requests
from thefuzz import fuzz

from jarvis.api import BaseTool, ToolInput, ToolOutput
from .types import ToolResult

EXAMPLE_PATTERNS = [
    "scripts",
    "examples",
    "example",
    "notebooks",
    "notebook",
    "tutorials",
    "tutorial",
    "quickstart",
    "walkthroughs",
    "walkthrough",
    "cookbook",
    "cookbooks",
    "recipes",
    "recipe",
    "demos",
    "demo",
    "samples",
    "sample",
    "guides",
    "guide",
    "getting-started",
    "getting_started",
    "playground",
    "howto",
    "how-to",
    "use-cases",
    "usecases",
    "use_cases",
    "sandbox",
    "showcase",
]


def _get_repo_tree(org: str, repo: str, token: str) -> tuple[List[Dict[str, Any]], str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    full_repo = f"{org}/{repo}"

    try:
        response = requests.get(
            f"https://api.github.com/repos/{full_repo}", headers=headers, timeout=10
        )
        if response.status_code == 404:
            return [], "not_found"
        if response.status_code != 200:
            return [], f"API error: {response.status_code}"

        repo_data = response.json()
        default_branch = repo_data.get("default_branch", "main")
    except Exception as e:
        return [], f"Error fetching repo: {str(e)}"

    try:
        response = requests.get(
            f"https://api.github.com/repos/{full_repo}/git/trees/{default_branch}",
            headers=headers,
            params={"recursive": "1"},
            timeout=30,
        )
        if response.status_code != 200:
            return [], f"Error fetching tree: {response.status_code}"

        data = response.json()
        tree = data.get("tree", [])

        files = [
            {
                "path": item["path"],
                "ref": item["sha"],
                "size": item.get("size", 0),
                "url": f"https://github.com/{full_repo}/blob/{default_branch}/{item['path']}",
            }
            for item in tree
            if item["type"] == "blob"
        ]

        return files, ""
    except Exception as e:
        return [], f"Error processing tree: {str(e)}"


def _search_similar_repos(org: str, repo: str, token: str) -> List[Dict[str, Any]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    query = f"org:{org} {repo}"

    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 10},
            timeout=30,
        )

        if response.status_code != 200:
            return []

        data = response.json()
        items = data.get("items", [])

        return [
            {
                "name": item.get("name"),
                "full_name": item.get("full_name"),
                "description": item.get("description"),
                "stars": item.get("stargazers_count", 0),
                "url": item.get("html_url"),
            }
            for item in items
        ]
    except Exception:
        return []


def _score_against_example_patterns(file_path: str) -> int:
    scores = []
    for pattern in EXAMPLE_PATTERNS:
        score = fuzz.token_set_ratio(pattern.lower(), file_path.lower())
        scores.append(score)
    return max(scores) if scores else 0


def _score_against_keyword(file_path: str, keyword: str) -> int:
    partial_score = fuzz.partial_ratio(keyword.lower(), file_path.lower())
    token_score = fuzz.token_set_ratio(keyword.lower(), file_path.lower())
    return max(partial_score, token_score)


def _get_pattern_priority(file_path: str) -> tuple[int, int, int]:
    path_lower = file_path.lower()
    path_parts = path_lower.split("/")

    in_examples_dir = 0 if (path_parts[0] in ["examples", "example"]) else 1

    best_priority = 999
    best_depth_at_match = -1

    for i, pattern in enumerate(EXAMPLE_PATTERNS):
        if pattern in path_parts:
            depth = len(path_parts) - 1 - path_parts[::-1].index(pattern)
            if depth > best_depth_at_match or (
                depth == best_depth_at_match and i < best_priority
            ):
                best_priority = i
                best_depth_at_match = depth

    return (in_examples_dir, best_priority, len(path_parts))


def _handle_repo_tree_errors(
    all_files: List[Dict[str, Any]],
    error: str,
    org: str,
    repo: str,
    token: str,
) -> ToolResult | None:
    if error == "not_found":
        similar_repos = _search_similar_repos(org, repo, token)

        if not similar_repos:
            return {
                "formatted": f"Repository '{org}/{repo}' not found and no similar repositories found.",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

        lines = [f"**Repository '{org}/{repo}' not found. Similar repositories:**\n"]
        for i, r in enumerate(similar_repos, 1):
            lines.append(f"{i}. **{r['full_name']}** (⭐ {r['stars']:,} stars)")
            if r["description"]:
                desc = (
                    r["description"][:100] + "..."
                    if len(r["description"]) > 100
                    else r["description"]
                )
                lines.append(f"   {desc}")
            lines.append(f"   {r['url']}\n")

        return {
            "formatted": "\n".join(lines),
            "totalResults": len(similar_repos),
            "resultsShared": len(similar_repos),
            "isError": True,
        }

    if error:
        return {
            "formatted": f"Error accessing repository '{org}/{repo}': {error}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if not all_files:
        return {
            "formatted": f"No files found in repository '{org}/{repo}'",
            "totalResults": 0,
            "resultsShared": 0,
        }

    return None


def find_examples(
    keyword: str = "",
    repo: str = "",
    org: str = "huggingface",
    max_results: int = 10,
    min_score: int = 80,
) -> ToolResult:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if not repo:
        return {
            "formatted": "Error: repo parameter is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    all_files, error = _get_repo_tree(org, repo, token)

    if error_result := _handle_repo_tree_errors(all_files, error, org, repo, token):
        return error_result

    example_threshold = 60
    example_files = []
    for file in all_files:
        example_score = _score_against_example_patterns(file["path"])
        if example_score >= example_threshold:
            example_files.append({**file, "example_score": example_score})

    if not example_files:
        return {
            "formatted": f"No example files found in {org}/{repo} (no files match example patterns with score >= {example_threshold}).",
            "totalResults": 0,
            "resultsShared": 0,
        }

    if keyword:
        scored_files = []
        for file in example_files:
            keyword_score = _score_against_keyword(file["path"], keyword)
            if keyword_score >= min_score:
                scored_files.append({**file, "score": keyword_score})

        if not scored_files:
            return {
                "formatted": f"No files found in {org}/{repo} matching keyword '{keyword}' (min score: {min_score}) among {len(example_files)} example files.",
                "totalResults": 0,
                "resultsShared": 0,
            }

        scored_files.sort(key=lambda x: x["score"], reverse=True)
    else:
        scored_files = []
        for file in example_files:
            in_examples_dir, pattern_priority, path_depth = _get_pattern_priority(
                file["path"]
            )
            scored_files.append(
                {
                    **file,
                    "score": file["example_score"],
                    "in_examples_dir": in_examples_dir,
                    "pattern_priority": pattern_priority,
                    "path_depth": path_depth,
                }
            )

        if not scored_files:
            return {
                "formatted": f"No example files found in {org}/{repo}.",
                "totalResults": 0,
                "resultsShared": 0,
            }

        scored_files.sort(
            key=lambda x: (
                x["in_examples_dir"],
                x["pattern_priority"],
                x["path_depth"],
                x["path"],
            )
        )

    results = scored_files[:max_results]

    keyword_desc = f" matching '{keyword}'" if keyword else ""
    lines = [f"**Found {len(results)} example files in {org}/{repo}{keyword_desc}:**"]
    if len(scored_files) > max_results:
        lines[0] += f" (showing {max_results} of {len(scored_files)})"
    lines.append("")

    for i, file in enumerate(results, 1):
        lines.append(f"{i}. **{file['path']}**")
        lines.append(f"   Size: {file['size']:,} bytes | Ref: {file['ref'][:7]}")
        lines.append(f"   URL: {file['url']}")

        read_params = f"{{'repo': '{org}/{repo}', 'path': '{file['path']}'}}"
        lines.append(f"   To read, use: {read_params}")
        lines.append("")

    return {
        "formatted": "\n".join(lines),
        "totalResults": len(results),
        "resultsShared": len(results),
    }


GITHUB_FIND_EXAMPLES_TOOL_SPEC = {
    "name": "github_find_examples",
    "description": (
        "Find working example scripts in GitHub repositories (from a list of predetermined directories e.g. examples/, scripts/, tutorials/, etc.). "
        "Uses fuzzy keyword matching.\n\n"
        "MANDATORY before writing any ML training, fine-tuning, or inference code. "
        "Your internal knowledge of library APIs is outdated — working examples show current API patterns.\n\n"
        "Sequence: github_find_examples → github_read_file (study the example) → implement based on what you found.\n\n"
        "Skip this only for: simple data queries, status checks, non-code tasks.\n\n"
        "Examples:\n"
        "  {keyword: 'sft', repo: 'trl'} → finds examples/scripts/sft.py\n"
        "  {keyword: 'grpo', repo: 'trl'} → finds GRPO training examples\n"
        "  {repo: 'trl', max_results: 20} → lists all available training method examples"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Keyword to fuzzy match against file paths (e.g., 'grpo', 'sft').",
            },
            "repo": {
                "type": "string",
                "description": "Repository name (e.g., 'trl', 'transformers'). Required.",
            },
            "org": {
                "type": "string",
                "description": "GitHub organization or username. Default: 'huggingface'.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Default: 50.",
            },
            "min_score": {
                "type": "integer",
                "description": "Minimum fuzzy match score (0-100). Default: 60.",
            },
        },
        "required": ["repo"],
    },
}


async def github_find_examples_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = find_examples(
            keyword=arguments.get("keyword", ""),
            repo=arguments["repo"],
            org=arguments.get("org", "huggingface"),
            max_results=arguments.get("max_results", 50),
            min_score=arguments.get("min_score", 60),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error finding examples: {str(e)}", False


class GithubFindExamplesTool(BaseTool):
    name = GITHUB_FIND_EXAMPLES_TOOL_SPEC["name"]
    description = GITHUB_FIND_EXAMPLES_TOOL_SPEC["description"]
    input_schema = GITHUB_FIND_EXAMPLES_TOOL_SPEC["parameters"]

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        args: Dict[str, Any] = {}
        for key in ("keyword", "repo", "org", "max_results", "min_score"):
            val = getattr(input_data, key, None)
            if val is not None:
                args[key] = val
        if "repo" not in args:
            return ToolOutput(success=False, result=None, error="repo is required")

        try:
            result, success = await github_find_examples_handler(args)
            return ToolOutput(success=success, result=result)
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")
