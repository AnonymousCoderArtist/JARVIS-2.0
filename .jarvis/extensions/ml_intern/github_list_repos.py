"""GitHub List Repositories Tool - List and sort repositories for any user or organization

Efficiently discover repositories with flexible sorting options.
"""

import os
from typing import Any, Dict, Literal, Optional

import requests

from jarvis.api import BaseTool, ToolInput, ToolOutput
from .types import ToolResult


def list_repos(
    owner: str,
    owner_type: Literal["user", "org"] = "org",
    sort: Literal["stars", "forks", "updated", "created"] = "stars",
    order: Literal["asc", "desc"] = "desc",
    limit: Optional[int] = 30,
) -> ToolResult:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {
            "formatted": "Error: GITHUB_TOKEN environment variable is required",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if owner_type == "org":
        url = f"https://api.github.com/orgs/{owner}/repos"
    else:
        url = f"https://api.github.com/users/{owner}/repos"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    all_repos = []
    page = 1
    per_page = 100

    api_sort_map = {
        "created": "created",
        "updated": "updated",
        "stars": None,
        "forks": None,
    }

    api_sort = api_sort_map.get(sort)
    need_manual_sort = api_sort is None

    try:
        while True:
            params = {
                "page": page,
                "per_page": per_page,
            }

            if api_sort:
                params["sort"] = api_sort
                params["direction"] = order

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 403:
                error_data = response.json()
                return {
                    "formatted": f"GitHub API rate limit or permission error: {error_data.get('message', 'Unknown error')}",
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }

            if response.status_code != 200:
                error_msg = f"GitHub API error (status {response.status_code})"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg += f": {error_data['message']}"
                except Exception:
                    pass
                return {
                    "formatted": error_msg,
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }

            items = response.json()

            if not items:
                break

            for item in items:
                all_repos.append(
                    {
                        "name": item.get("name"),
                        "full_name": item.get("full_name"),
                        "description": item.get("description"),
                        "html_url": item.get("html_url"),
                        "language": item.get("language"),
                        "stars": item.get("stargazers_count", 0),
                        "forks": item.get("forks_count", 0),
                        "open_issues": item.get("open_issues_count", 0),
                        "topics": item.get("topics", []),
                        "updated_at": item.get("updated_at"),
                        "created_at": item.get("created_at"),
                    }
                )

            if len(items) < per_page:
                break

            if limit and len(all_repos) >= limit:
                break

            page += 1

    except requests.exceptions.RequestException as e:
        return {
            "formatted": f"Failed to connect to GitHub API: {str(e)}",
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }

    if need_manual_sort and all_repos:
        reverse = order == "desc"
        all_repos.sort(key=lambda x: x[sort], reverse=reverse)

    if limit:
        all_repos = all_repos[:limit]

    if not all_repos:
        return {
            "formatted": f"No repositories found for {owner_type} '{owner}'",
            "totalResults": 0,
            "resultsShared": 0,
        }

    lines = [f"**Found {len(all_repos)} repositories for {owner}:**\n"]

    for i, repo in enumerate(all_repos, 1):
        lines.append(f"{i}. **{repo['full_name']}**")
        lines.append(
            f"   ⭐ {repo['stars']:,} stars | 🍴 {repo['forks']:,} forks | Language: {repo['language'] or 'N/A'}"
        )
        if repo["description"]:
            desc = (
                repo["description"][:100] + "..."
                if len(repo["description"]) > 100
                else repo["description"]
            )
            lines.append(f"   {desc}")
        lines.append(f"   URL: {repo['html_url']}")
        if repo["topics"]:
            lines.append(f"   Topics: {', '.join(repo['topics'][:5])}")

        lines.append(f"   Use in tools: {{'repo': '{repo['full_name']}'}}")
        lines.append("")

    return {
        "formatted": "\n".join(lines),
        "totalResults": len(all_repos),
        "resultsShared": len(all_repos),
    }


GITHUB_LIST_REPOS_TOOL_SPEC = {
    "name": "github_list_repos",
    "description": (
        "List and discover repositories for GitHub organizations or users with flexible sorting. "
        "**Use when:** (1) Exploring what libraries exist for a task, (2) Finding the right library to use, "
        "(3) Discovering popular or active projects, (4) Checking recently updated repos for latest features, "
        "(5) Finding alternative libraries in an organization. "
        "**Pattern:** github_list_repos (discover libraries) → github_find_examples (find usage examples) → implement. "
        "Returns: Comprehensive repository information (stars, forks, language, topics, URLs), sorted by preference. "
        "**Then:** Use github_find_examples on selected repo to discover example code. "
        "Sorts by: stars (popularity), forks (community), updated (activity), created (age)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "GitHub username or organization name. Required.",
            },
            "owner_type": {
                "type": "string",
                "enum": ["user", "org"],
                "description": "Whether the owner is a 'user' or 'org'. Default: 'org'.",
            },
            "sort": {
                "type": "string",
                "enum": ["stars", "forks", "updated", "created"],
                "description": "Sort field. Options: 'stars', 'forks', 'updated', 'created'. Default: 'stars'.",
            },
            "order": {
                "type": "string",
                "enum": ["asc", "desc"],
                "description": "Sort order. Options: 'asc', 'desc'. Default: 'desc'.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of repositories to return. No limit if not specified. Default: 30.",
            },
        },
        "required": ["owner"],
    },
}


async def github_list_repos_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    """Handler for agent tool router"""
    try:
        result = list_repos(
            owner=arguments["owner"],
            owner_type=arguments.get("owner_type", "org"),
            sort=arguments.get("sort", "stars"),
            order=arguments.get("order", "desc"),
            limit=arguments.get("limit"),
        )
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error listing repositories: {str(e)}", False


class GithubListReposTool(BaseTool):
    name = GITHUB_LIST_REPOS_TOOL_SPEC["name"]
    description = GITHUB_LIST_REPOS_TOOL_SPEC["description"]
    input_schema = GITHUB_LIST_REPOS_TOOL_SPEC["parameters"]

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        args: Dict[str, Any] = {}
        for key in ("owner", "owner_type", "sort", "order", "limit"):
            val = getattr(input_data, key, None)
            if val is not None:
                args[key] = val
        if "owner" not in args:
            return ToolOutput(success=False, result=None, error="owner is required")

        try:
            result, success = await github_list_repos_handler(args)
            return ToolOutput(success=success, result=result)
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")
