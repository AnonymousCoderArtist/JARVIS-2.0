"""GitHub tools — find examples, list repos, read files.

Ported from huggingface/ml-intern agent/tools/github_*.py.
Three tools: github_find_examples, github_list_repos, github_read_file.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests as _requests

from jarvis.api import BaseTool, ToolInput, ToolOutput


# ---------------------------------------------------------------------------
# github_find_examples
# ---------------------------------------------------------------------------

# Predetermined directories in HF repos that typically contain examples
_EXAMPLE_DIRS = ["examples", "scripts", "tutorials", "notebooks", "docs/source"]


def _fuzzy_match(query: str, text: str) -> int:
    """Simple fuzzy match score (0-100)."""
    if not query:
        return 100
    q = query.lower()
    t = text.lower()
    if q in t:
        return 100
    # Check each word
    words = q.split()
    if all(w in t for w in words):
        return 80
    # Partial match
    matches = sum(1 for c in q if c in t)
    return int(matches / len(q) * 60) if q else 0


def _find_examples(keyword: str, repo: str, org: str = "huggingface", max_results: int = 50, min_score: int = 60) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"formatted": "Error: GITHUB_TOKEN not set", "isError": True}

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    # Get the default branch
    repo_url = f"https://api.github.com/repos/{org}/{repo}"
    repo_resp = _requests.get(repo_url, headers=headers, timeout=30)
    if repo_resp.status_code != 200:
        return {"formatted": f"Error: repo {org}/{repo} not found", "isError": True}
    default_branch = repo_resp.json().get("default_branch", "main")

    # Search for example files in common directories
    all_files: list[dict[str, Any]] = []
    for example_dir in _EXAMPLE_DIRS:
        url = f"https://api.github.com/repos/{org}/{repo}/git/trees/{default_branch}?recursive=1"
        resp = _requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            continue
        tree = resp.json().get("tree", [])
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if not path.startswith(example_dir):
                continue
            if not path.endswith(".py"):
                continue
            score = _fuzzy_match(keyword, path)
            if score >= min_score:
                all_files.append({"path": path, "score": score, "size": item.get("size", 0)})

    # Sort by score descending
    all_files.sort(key=lambda x: x["score"], reverse=True)
    all_files = all_files[:max_results]

    if not all_files:
        return {"formatted": f"No example files found matching '{keyword}' in {org}/{repo}", "totalResults": 0, "resultsShared": 0}

    lines = [f"# Example files in {org}/{repo}", f"Keyword: '{keyword}' — Showing {len(all_files)} result(s)\n"]
    for i, f in enumerate(all_files, 1):
        lines.append(f"{i}. **{f['path']}** (score: {f['score']})")
        lines.append(f"   Use: github_read_file(repo='{org}/{repo}', path='{f['path']}')")
        lines.append("")

    return {"formatted": "\n".join(lines), "totalResults": len(all_files), "resultsShared": len(all_files)}


class GithubFindExamplesTool(BaseTool):
    name = "github_find_examples"
    description = (
        "Find working example scripts in GitHub repositories (from a list of predetermined directories e.g. examples/, scripts/, tutorials/, etc.). "
        "Uses fuzzy keyword matching.\n\n"
        "MANDATORY before writing any ML training, fine-tuning, or inference code. "
        "Your internal knowledge of library APIs is outdated — working examples show current API patterns.\n\n"
        "Sequence: github_find_examples → github_read_file (study the example) → implement based on what you found.\n\n"
        "Skip this only for: simple data queries, status checks, non-code tasks."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Keyword to fuzzy match against file paths (e.g., 'grpo', 'sft')."},
            "repo": {"type": "string", "description": "Repository name (e.g., 'trl', 'transformers'). Required."},
            "org": {"type": "string", "description": "GitHub organization or username. Default: 'huggingface'."},
            "max_results": {"type": "integer", "description": "Maximum number of results to return. Default: 50."},
            "min_score": {"type": "integer", "description": "Minimum fuzzy match score (0-100). Default: 60."},
        },
        "required": ["repo"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        keyword = input_data.query or ""
        repo = getattr(input_data, "repo", None) or ""
        org = getattr(input_data, "org", "huggingface")
        max_results = getattr(input_data, "max_results", 50)
        min_score = getattr(input_data, "min_score", 60)

        if not repo:
            return ToolOutput(success=False, result=None, error="repo is required")

        try:
            result = _find_examples(keyword=keyword, repo=repo, org=org, max_results=max_results, min_score=min_score)
            return ToolOutput(success=not result.get("isError", False), result=result["formatted"])
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")


# ---------------------------------------------------------------------------
# github_list_repos
# ---------------------------------------------------------------------------

def _list_repos(owner: str, owner_type: str = "org", sort: str = "stars", order: str = "desc", limit: int = 30) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"formatted": "Error: GITHUB_TOKEN not set", "isError": True}

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    url = f"https://api.github.com/orgs/{owner}/repos" if owner_type == "org" else f"https://api.github.com/users/{owner}/repos"

    all_repos: list[dict[str, Any]] = []
    page = 1
    per_page = 100
    need_manual_sort = sort in ("stars", "forks")

    try:
        while True:
            params: dict[str, Any] = {"page": page, "per_page": per_page}
            if not need_manual_sort:
                params["sort"] = sort
                params["direction"] = order

            response = _requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                error_msg = f"GitHub API error (status {response.status_code})"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg += f": {error_data['message']}"
                except Exception:
                    pass
                return {"formatted": error_msg, "isError": True}

            items = response.json()
            if not items:
                break

            for item in items:
                all_repos.append({
                    "name": item.get("name"),
                    "full_name": item.get("full_name"),
                    "description": item.get("description"),
                    "html_url": item.get("html_url"),
                    "language": item.get("language"),
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "topics": item.get("topics", []),
                    "updated_at": item.get("updated_at"),
                })

            if len(items) < per_page or (limit and len(all_repos) >= limit):
                break
            page += 1

    except _requests.exceptions.RequestException as e:
        return {"formatted": f"Failed to connect to GitHub API: {e}", "isError": True}

    if need_manual_sort and all_repos:
        reverse = order == "desc"
        all_repos.sort(key=lambda x: x[sort], reverse=reverse)

    if limit:
        all_repos = all_repos[:limit]

    if not all_repos:
        return {"formatted": f"No repositories found for {owner_type} '{owner}'", "totalResults": 0, "resultsShared": 0}

    lines = [f"**Found {len(all_repos)} repositories for {owner}:**\n"]
    for i, repo in enumerate(all_repos, 1):
        lines.append(f"{i}. **{repo['full_name']}**")
        lines.append(f"   {repo['stars']:,} stars | {repo['forks']:,} forks | Language: {repo['language'] or 'N/A'}")
        if repo["description"]:
            desc = repo["description"][:100] + "..." if len(repo["description"]) > 100 else repo["description"]
            lines.append(f"   {desc}")
        lines.append(f"   URL: {repo['html_url']}")
        if repo["topics"]:
            lines.append(f"   Topics: {', '.join(repo['topics'][:5])}")
        lines.append("")

    return {"formatted": "\n".join(lines), "totalResults": len(all_repos), "resultsShared": len(all_repos)}


class GithubListReposTool(BaseTool):
    name = "github_list_repos"
    description = (
        "List and discover repositories for GitHub organizations or users with flexible sorting. "
        "Use when exploring what libraries exist for a task, finding the right library, or discovering popular projects. "
        "Pattern: github_list_repos (discover libraries) → github_find_examples (find usage examples) → implement."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "GitHub username or organization name. Required."},
            "owner_type": {"type": "string", "enum": ["user", "org"], "description": "Whether the owner is a 'user' or 'org'. Default: 'org'."},
            "sort": {"type": "string", "enum": ["stars", "forks", "updated", "created"], "description": "Sort field. Default: 'stars'."},
            "order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order. Default: 'desc'."},
            "limit": {"type": "integer", "description": "Maximum number of repositories to return. Default: 30."},
        },
        "required": ["owner"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        owner = input_data.query or ""
        owner_type = getattr(input_data, "owner_type", "org")
        sort = getattr(input_data, "sort", "stars")
        order = getattr(input_data, "order", "desc")
        limit = getattr(input_data, "limit", 30)

        if not owner:
            return ToolOutput(success=False, result=None, error="owner is required")

        try:
            result = _list_repos(owner=owner, owner_type=owner_type, sort=sort, order=order, limit=limit)
            return ToolOutput(success=not result.get("isError", False), result=result["formatted"])
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")


# ---------------------------------------------------------------------------
# github_read_file
# ---------------------------------------------------------------------------

def _convert_ipynb_to_markdown(content: str) -> str:
    """Convert Jupyter notebook JSON to markdown. Falls back to raw content on error."""
    try:
        import nbformat
        from nbconvert import MarkdownExporter
        from nbconvert.preprocessors import ClearOutputPreprocessor, TagRemovePreprocessor

        nb_dict = json.loads(content)
        if "cells" in nb_dict:
            for cell in nb_dict["cells"]:
                if "source" in cell and isinstance(cell["source"], list):
                    cell["source"] = "".join(cell["source"])
        nb = nbformat.reads(json.dumps(nb_dict), as_version=4)
        clear = ClearOutputPreprocessor()
        nb, _ = clear.preprocess(nb, {})
        remove = TagRemovePreprocessor(remove_cell_tags={"hide", "hidden", "remove"}, remove_input_tags=set(), remove_all_outputs_tags=set())
        nb, _ = remove.preprocess(nb, {})
        exporter = MarkdownExporter()
        markdown, _ = exporter.from_notebook_node(nb)
        return markdown
    except Exception:
        return content


def _read_file(repo: str, path: str, ref: str = "HEAD", line_start: int | None = None, line_end: int | None = None) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"formatted": "Error: GITHUB_TOKEN not set", "isError": True}

    if "/" not in repo:
        return {"formatted": "Error: repo must be in format 'owner/repo'", "isError": True}

    owner, repo_name = repo.split("/", 1)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
    params: dict[str, Any] = {}
    if ref and ref != "HEAD":
        params["ref"] = ref

    try:
        response = _requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 404:
            return {"formatted": f"File not found: {path} in {repo}", "isError": True}
        if response.status_code != 200:
            return {"formatted": f"GitHub API error (status {response.status_code})", "isError": True}

        data = response.json()
        if data.get("type") != "file":
            return {"formatted": f"Path {path} is not a file (type: {data.get('type')})", "isError": True}

        content_b64 = data.get("content", "")
        if content_b64:
            content_b64 = content_b64.replace("\n", "").replace(" ", "")
            content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        else:
            raw_headers = {"Accept": "application/vnd.github.raw", "X-GitHub-Api-Version": "2022-11-28", "Authorization": f"Bearer {token}"}
            raw_response = _requests.get(url, headers=raw_headers, params=params, timeout=30)
            if raw_response.status_code != 200:
                return {"formatted": "Failed to fetch file content", "isError": True}
            content = raw_response.text

        if path.lower().endswith(".ipynb"):
            content = _convert_ipynb_to_markdown(content)

        lines = content.split("\n")
        total_lines = len(lines)
        truncated = False

        if line_start is None and line_end is None:
            if total_lines > 300:
                line_start = 1
                line_end = 300
                truncated = True
            else:
                line_start = 1
                line_end = total_lines
        else:
            if line_start is None:
                line_start = 1
            if line_end is None:
                line_end = total_lines
            line_start = max(1, line_start)
            line_end = min(total_lines, line_end)
            if line_start > line_end:
                return {"formatted": f"Invalid range: line_start ({line_start}) > line_end ({line_end})", "isError": True}

        selected_lines = lines[line_start - 1:line_end]
        selected_content = "\n".join(selected_lines)

        output = [f"**Reading file from repo: {repo}, path: {path}**"]
        if ref and ref != "HEAD":
            output.append(f"Ref: {ref}")
        output.append("\n**File content:")
        output.append("```")
        output.append(selected_content)
        output.append("```")
        if truncated:
            output.append(f"Currently showing lines {line_start}-{line_end} out of {total_lines} total lines. Use line_start and line_end to view more lines.")

        return {"formatted": "\n".join(output), "totalResults": 1, "resultsShared": 1}

    except _requests.exceptions.RequestException as e:
        return {"formatted": f"Failed to connect to GitHub API: {e}", "isError": True}


class GithubReadFileTool(BaseTool):
    name = "github_read_file"
    description = (
        "Read file contents from GitHub repositories. Returns first 300 lines by default. "
        "Auto-converts Jupyter notebooks to markdown.\n\n"
        "Use AFTER github_find_examples to study the working implementation. "
        "The purpose is to learn current API patterns — imports, trainer configs, dataset handling — "
        "so your implementation uses correct, up-to-date code.\n\n"
        "Use line_start/line_end for large files (>300 lines) to read specific sections."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository in format 'owner/repo' (e.g., 'huggingface/trl'). Required."},
            "path": {"type": "string", "description": "Path to file in repository (e.g., 'examples/scripts/sft.py'). Required."},
            "ref": {"type": "string", "description": "Git reference - branch name, tag, or commit SHA. Default: 'HEAD'."},
            "line_start": {"type": "integer", "description": "Starting line number (1-indexed, inclusive). Optional."},
            "line_end": {"type": "integer", "description": "Ending line number (1-indexed, inclusive). Optional."},
        },
        "required": ["repo", "path"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        repo = input_data.query or ""
        path = getattr(input_data, "path", None) or ""
        ref = getattr(input_data, "ref", "HEAD")
        line_start = getattr(input_data, "line_start", None)
        line_end = getattr(input_data, "line_end", None)

        if not repo:
            return ToolOutput(success=False, result=None, error="repo is required")
        if not path:
            return ToolOutput(success=False, result=None, error="path is required")

        try:
            result = _read_file(repo=repo, path=path, ref=ref, line_start=line_start, line_end=line_end)
            return ToolOutput(success=not result.get("isError", False), result=result["formatted"])
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")
