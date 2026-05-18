"""HF Repo Git Tool - Git-like operations on Hugging Face repositories

Operations: branches, tags, PRs, repo management
"""

import asyncio
import os
from typing import Any, Dict, Literal, Optional

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from jarvis.api import BaseTool, ToolInput, ToolOutput
from .types import ToolResult

OperationType = Literal[
    "create_branch",
    "delete_branch",
    "create_tag",
    "delete_tag",
    "list_refs",
    "create_pr",
    "list_prs",
    "get_pr",
    "merge_pr",
    "close_pr",
    "comment_pr",
    "change_pr_status",
    "create_repo",
    "update_repo",
]


async def _async_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _build_repo_url(repo_id: str, repo_type: str = "model") -> str:
    if repo_type == "model":
        return f"https://huggingface.co/{repo_id}"
    return f"https://huggingface.co/{repo_type}s/{repo_id}"


class _HfRepoGitInternal:
    """Tool for git-like operations on HF repos."""

    def __init__(self, hf_token: Optional[str] = None, session: Any = None):
        self.api = HfApi(token=hf_token)
        self.session = session

    async def execute(self, args: Dict[str, Any]) -> ToolResult:
        operation = args.get("operation")

        if not operation:
            return self._help()

        try:
            handlers = {
                "create_branch": self._create_branch,
                "delete_branch": self._delete_branch,
                "create_tag": self._create_tag,
                "delete_tag": self._delete_tag,
                "list_refs": self._list_refs,
                "create_pr": self._create_pr,
                "list_prs": self._list_prs,
                "get_pr": self._get_pr,
                "merge_pr": self._merge_pr,
                "close_pr": self._close_pr,
                "comment_pr": self._comment_pr,
                "change_pr_status": self._change_pr_status,
                "create_repo": self._create_repo,
                "update_repo": self._update_repo,
            }

            handler = handlers.get(operation)
            if handler:
                return await handler(args)
            else:
                ops = ", ".join(handlers.keys())
                return self._error(f"Unknown operation: {operation}. Valid: {ops}")

        except RepositoryNotFoundError:
            return self._error(f"Repository not found: {args.get('repo_id')}")
        except Exception as e:
            return self._error(f"Error: {str(e)}")

    def _help(self) -> ToolResult:
        return {
            "formatted": """**hf_repo_git** - Git-like operations on HF repos

**Branch/Tag:**
- `create_branch`: `{"operation": "create_branch", "repo_id": "...", "branch": "dev"}`
- `delete_branch`: `{"operation": "delete_branch", "repo_id": "...", "branch": "dev"}`
- `create_tag`: `{"operation": "create_tag", "repo_id": "...", "tag": "v1.0"}`
- `delete_tag`: `{"operation": "delete_tag", "repo_id": "...", "tag": "v1.0"}`
- `list_refs`: `{"operation": "list_refs", "repo_id": "..."}`

**PRs:**
- `create_pr`: `{"operation": "create_pr", "repo_id": "...", "title": "..."}` (creates draft PR)
- `list_prs`: `{"operation": "list_prs", "repo_id": "..."}` (shows status: draft/open/merged/closed)
- `get_pr`: `{"operation": "get_pr", "repo_id": "...", "pr_num": 1}`
- `change_pr_status`: `{"operation": "change_pr_status", "repo_id": "...", "pr_num": 1, "new_status": "open"}`
- `merge_pr`: `{"operation": "merge_pr", "repo_id": "...", "pr_num": 1}`
- `close_pr`: `{"operation": "close_pr", "repo_id": "...", "pr_num": 1}`
- `comment_pr`: `{"operation": "comment_pr", "repo_id": "...", "pr_num": 1, "comment": "..."}`

**Repo:**
- `create_repo`: `{"operation": "create_repo", "repo_id": "my-model", "private": true}`
- `update_repo`: `{"operation": "update_repo", "repo_id": "...", "private": false}`""",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _create_branch(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        branch = args.get("branch")

        if not repo_id:
            return self._error("repo_id is required")
        if not branch:
            return self._error("branch is required")

        repo_type = args.get("repo_type", "model")
        from_rev = args.get("from_rev", "main")

        await _async_call(
            self.api.create_branch,
            repo_id=repo_id,
            branch=branch,
            revision=from_rev,
            repo_type=repo_type,
            exist_ok=args.get("exist_ok", False),
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/tree/{branch}"
        return {
            "formatted": f"**Branch created:** {branch}\n{url}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _delete_branch(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        branch = args.get("branch")

        if not repo_id:
            return self._error("repo_id is required")
        if not branch:
            return self._error("branch is required")

        repo_type = args.get("repo_type", "model")

        await _async_call(
            self.api.delete_branch,
            repo_id=repo_id,
            branch=branch,
            repo_type=repo_type,
        )

        return {
            "formatted": f"**Branch deleted:** {branch}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _create_tag(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        tag = args.get("tag")

        if not repo_id:
            return self._error("repo_id is required")
        if not tag:
            return self._error("tag is required")

        repo_type = args.get("repo_type", "model")
        revision = args.get("revision", "main")
        tag_message = args.get("tag_message", "")

        await _async_call(
            self.api.create_tag,
            repo_id=repo_id,
            tag=tag,
            revision=revision,
            tag_message=tag_message,
            repo_type=repo_type,
            exist_ok=args.get("exist_ok", False),
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/tree/{tag}"
        return {
            "formatted": f"**Tag created:** {tag}\n{url}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _delete_tag(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        tag = args.get("tag")

        if not repo_id:
            return self._error("repo_id is required")
        if not tag:
            return self._error("tag is required")

        repo_type = args.get("repo_type", "model")

        await _async_call(
            self.api.delete_tag,
            repo_id=repo_id,
            tag=tag,
            repo_type=repo_type,
        )

        return {
            "formatted": f"**Tag deleted:** {tag}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _list_refs(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "model")

        refs = await _async_call(
            self.api.list_repo_refs,
            repo_id=repo_id,
            repo_type=repo_type,
        )

        branches = [b.name for b in refs.branches] if refs.branches else []
        tags = (
            [t.name for t in refs.tags] if hasattr(refs, "tags") and refs.tags else []
        )

        url = _build_repo_url(repo_id, repo_type)
        lines = [f"**{repo_id}**", url, ""]

        if branches:
            lines.append(f"**Branches ({len(branches)}):** " + ", ".join(branches))
        else:
            lines.append("**Branches:** none")

        if tags:
            lines.append(f"**Tags ({len(tags)}):** " + ", ".join(tags))
        else:
            lines.append("**Tags:** none")

        return {
            "formatted": "\n".join(lines),
            "totalResults": len(branches) + len(tags),
            "resultsShared": len(branches) + len(tags),
        }

    async def _create_pr(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        title = args.get("title")

        if not repo_id:
            return self._error("repo_id is required")
        if not title:
            return self._error("title is required")

        repo_type = args.get("repo_type", "model")
        description = args.get("description", "")

        result = await _async_call(
            self.api.create_pull_request,
            repo_id=repo_id,
            title=title,
            description=description,
            repo_type=repo_type,
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{result.num}"
        return {
            "formatted": f'**Draft PR #{result.num} created:** {title}\n{url}\n\nAdd commits via upload with revision="refs/pr/{result.num}"',
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _list_prs(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "model")
        status = args.get("status", "all")

        discussions = list(
            self.api.get_repo_discussions(
                repo_id=repo_id,
                repo_type=repo_type,
                discussion_status=status if status != "all" else None,
            )
        )

        if not discussions:
            return {
                "formatted": f"No discussions in {repo_id}",
                "totalResults": 0,
                "resultsShared": 0,
            }

        url = _build_repo_url(repo_id, repo_type)
        lines = [
            f"**{repo_id}** - {len(discussions)} discussions",
            f"{url}/discussions",
            "",
        ]

        for d in discussions[:20]:
            if d.status == "draft":
                status_label = "[DRAFT]"
            elif d.status == "open":
                status_label = "[OPEN]"
            elif d.status == "merged":
                status_label = "[MERGED]"
            else:
                status_label = "[CLOSED]"
            type_label = "PR" if d.is_pull_request else "D"
            lines.append(f"{status_label} #{d.num} [{type_label}] {d.title}")

        return {
            "formatted": "\n".join(lines),
            "totalResults": len(discussions),
            "resultsShared": min(20, len(discussions)),
        }

    async def _get_pr(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        pr_num = args.get("pr_num")

        if not repo_id:
            return self._error("repo_id is required")
        if not pr_num:
            return self._error("pr_num is required")

        repo_type = args.get("repo_type", "model")

        pr = await _async_call(
            self.api.get_discussion_details,
            repo_id=repo_id,
            discussion_num=int(pr_num),
            repo_type=repo_type,
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        status_map = {
            "draft": "Draft",
            "open": "Open",
            "merged": "Merged",
            "closed": "Closed",
        }
        status = status_map.get(pr.status, pr.status.capitalize())
        type_label = "Pull Request" if pr.is_pull_request else "Discussion"

        lines = [
            f"**{type_label} #{pr_num}:** {pr.title}",
            f"**Status:** {status}",
            f"**Author:** {pr.author}",
            url,
        ]

        if pr.is_pull_request:
            if pr.status == "draft":
                lines.append(
                    f'\nTo add commits: upload with revision="refs/pr/{pr_num}"'
                )
            elif pr.status == "open":
                lines.append(
                    f'\nTo add commits: upload with revision="refs/pr/{pr_num}"'
                )

        return {"formatted": "\n".join(lines), "totalResults": 1, "resultsShared": 1}

    async def _merge_pr(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        pr_num = args.get("pr_num")

        if not repo_id:
            return self._error("repo_id is required")
        if not pr_num:
            return self._error("pr_num is required")

        repo_type = args.get("repo_type", "model")
        comment = args.get("comment", "")

        await _async_call(
            self.api.merge_pull_request,
            repo_id=repo_id,
            discussion_num=int(pr_num),
            comment=comment,
            repo_type=repo_type,
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        return {
            "formatted": f"**PR #{pr_num} merged**\n{url}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _close_pr(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        pr_num = args.get("pr_num")

        if not repo_id:
            return self._error("repo_id is required")
        if not pr_num:
            return self._error("pr_num is required")

        repo_type = args.get("repo_type", "model")
        comment = args.get("comment", "")

        await _async_call(
            self.api.change_discussion_status,
            repo_id=repo_id,
            discussion_num=int(pr_num),
            new_status="closed",
            comment=comment,
            repo_type=repo_type,
        )

        return {
            "formatted": f"**Discussion #{pr_num} closed**",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _comment_pr(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        pr_num = args.get("pr_num")
        comment = args.get("comment")

        if not repo_id:
            return self._error("repo_id is required")
        if not pr_num:
            return self._error("pr_num is required")
        if not comment:
            return self._error("comment is required")

        repo_type = args.get("repo_type", "model")

        await _async_call(
            self.api.comment_discussion,
            repo_id=repo_id,
            discussion_num=int(pr_num),
            comment=comment,
            repo_type=repo_type,
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        return {
            "formatted": f"**Comment added to #{pr_num}**\n{url}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _change_pr_status(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        pr_num = args.get("pr_num")
        new_status = args.get("new_status")

        if not repo_id:
            return self._error("repo_id is required")
        if not pr_num:
            return self._error("pr_num is required")
        if not new_status:
            return self._error("new_status is required (open or closed)")

        repo_type = args.get("repo_type", "model")
        comment = args.get("comment", "")

        await _async_call(
            self.api.change_discussion_status,
            repo_id=repo_id,
            discussion_num=int(pr_num),
            new_status=new_status,
            comment=comment,
            repo_type=repo_type,
        )

        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        return {
            "formatted": f"**PR #{pr_num} status changed to {new_status}**\n{url}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _create_repo(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "model")
        private = args.get("private", True)
        space_sdk = args.get("space_sdk")

        if repo_type == "space" and not space_sdk:
            return self._error(
                "space_sdk required for spaces (gradio/streamlit/docker/static)"
            )

        kwargs = {
            "repo_id": repo_id,
            "repo_type": repo_type,
            "private": private,
            "exist_ok": args.get("exist_ok", False),
        }
        if space_sdk:
            kwargs["space_sdk"] = space_sdk

        result = await _async_call(self.api.create_repo, **kwargs)

        return {
            "formatted": f"**Repository created:** {repo_id}\n**Private:** {private}\n{result}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _update_repo(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "model")
        private = args.get("private")
        gated = args.get("gated")

        if private is None and gated is None:
            return self._error(
                "Specify private (bool) or gated ('auto'/'manual'/false)"
            )

        kwargs = {"repo_id": repo_id, "repo_type": repo_type}
        if private is not None:
            kwargs["private"] = private
        if gated is not None:
            kwargs["gated"] = gated

        await _async_call(self.api.update_repo_settings, **kwargs)

        changes = []
        if private is not None:
            changes.append(f"private={private}")
        if gated is not None:
            changes.append(f"gated={gated}")

        url = f"{_build_repo_url(repo_id, repo_type)}/settings"
        return {
            "formatted": f"**Settings updated:** {', '.join(changes)}\n{url}",
            "totalResults": 1,
            "resultsShared": 1,
        }

    def _error(self, message: str) -> ToolResult:
        return {
            "formatted": message,
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }


HF_REPO_GIT_TOOL_SPEC = {
    "name": "hf_repo_git",
    "description": (
        "Git-like operations on HF repos: branches, tags, PRs, and repo management.\n\n"
        "## Operations\n"
        "**Branches:** create_branch, delete_branch, list_refs\n"
        "**Tags:** create_tag, delete_tag\n"
        "**PRs:** create_pr, list_prs, get_pr, merge_pr, close_pr, comment_pr, change_pr_status\n"
        "**Repo:** create_repo, update_repo\n\n"
        "## Notes\n"
        "- PR status: draft (default), open, merged, closed\n"
        "- For spaces, create_repo needs space_sdk (gradio/streamlit/docker/static)\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "create_branch",
                    "delete_branch",
                    "create_tag",
                    "delete_tag",
                    "list_refs",
                    "create_pr",
                    "list_prs",
                    "get_pr",
                    "merge_pr",
                    "close_pr",
                    "comment_pr",
                    "change_pr_status",
                    "create_repo",
                    "update_repo",
                ],
                "description": "Operation to execute",
            },
            "repo_id": {
                "type": "string",
                "description": "Repository ID (e.g., 'username/repo-name')",
            },
            "repo_type": {
                "type": "string",
                "enum": ["model", "dataset", "space"],
                "description": "Repository type (default: model)",
            },
            "branch": {
                "type": "string",
                "description": "Branch name (create_branch, delete_branch)",
            },
            "from_rev": {
                "type": "string",
                "description": "Create branch from this revision (default: main)",
            },
            "tag": {
                "type": "string",
                "description": "Tag name (create_tag, delete_tag)",
            },
            "revision": {
                "type": "string",
                "description": "Revision for tag (default: main)",
            },
            "title": {
                "type": "string",
                "description": "PR title (create_pr)",
            },
            "description": {
                "type": "string",
                "description": "PR description (create_pr)",
            },
            "pr_num": {
                "type": "integer",
                "description": "PR/discussion number",
            },
            "comment": {
                "type": "string",
                "description": "Comment text",
            },
            "status": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "description": "Filter PRs by status (list_prs)",
            },
            "new_status": {
                "type": "string",
                "enum": ["open", "closed"],
                "description": "New status for PR (change_pr_status)",
            },
            "private": {
                "type": "boolean",
                "description": "Make repo private (create_repo, update_repo)",
            },
            "gated": {
                "type": "string",
                "enum": ["auto", "manual", "false"],
                "description": "Gated access setting (update_repo)",
            },
            "space_sdk": {
                "type": "string",
                "enum": ["gradio", "streamlit", "docker", "static"],
                "description": "Space SDK (required for create_repo with space)",
            },
        },
        "required": ["operation"],
    },
}


async def hf_repo_git_handler(
    arguments: Dict[str, Any], session=None
) -> tuple[str, bool]:
    """Handler for agent tool router."""
    try:
        hf_token = session.hf_token if session else None
        tool = _HfRepoGitInternal(hf_token=hf_token, session=session)
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error: {str(e)}", False


class HfRepoGitTool(BaseTool):
    name = HF_REPO_GIT_TOOL_SPEC["name"]
    description = HF_REPO_GIT_TOOL_SPEC["description"]
    input_schema = HF_REPO_GIT_TOOL_SPEC["parameters"]

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        args: Dict[str, Any] = {}
        for key in ("operation", "repo_id", "repo_type", "branch", "from_rev", "tag", "revision",
                     "title", "description", "pr_num", "comment", "status", "new_status",
                     "private", "gated", "space_sdk", "tag_message", "exist_ok"):
            val = getattr(input_data, key, None)
            if val is not None:
                args[key] = val

        class _Session:
            hf_token = os.environ.get("HF_TOKEN")

        try:
            result, success = await hf_repo_git_handler(args, session=_Session())
            return ToolOutput(success=success, result=result)
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")
