"""HF Repo tools — file operations and git operations on HF repos.

Ported from huggingface/ml-intern agent/tools/hf_repo_files_tool.py and hf_repo_git_tool.py.
Two tools: hf_repo_files, hf_repo_git.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from jarvis.api import BaseTool, ToolInput, ToolOutput

# Lazy import — huggingface_hub may not be installed
_hf_hub = None


def _get_hf_api(token: str | None = None):
    global _hf_hub
    if _hf_hub is None:
        try:
            from huggingface_hub import HfApi, hf_hub_download
            _hf_hub = {"HfApi": HfApi, "hf_hub_download": hf_hub_download}
        except ImportError:
            raise RuntimeError("huggingface_hub is not installed. Run: pip install huggingface_hub")
    return _hf_hub["HfApi"](token=token)


async def _async_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _build_repo_url(repo_id: str, repo_type: str = "model") -> str:
    if repo_type == "model":
        return f"https://huggingface.co/{repo_id}"
    return f"https://huggingface.co/{repo_type}s/{repo_id}"


def _format_size(size_bytes: int) -> str:
    current: float = size_bytes
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if current < 1024:
            return f"{current:.1f}{unit}"
        current /= 1024
    return f"{current:.1f}PB"


# ---------------------------------------------------------------------------
# hf_repo_files
# ---------------------------------------------------------------------------

class HfRepoFilesTool(BaseTool):
    name = "hf_repo_files"
    description = (
        "Read and write files in HF repos (models/datasets/spaces).\n\n"
        "Operations:\n"
        "- list: List files with sizes and structure\n"
        "- read: Read file content (text files only)\n"
        "- upload: Upload content to repo (can create PR)\n"
        "- delete: Delete files/folders (supports wildcards like *.tmp)\n\n"
        "Use when you need to see what files exist in a repo, read config.json/README.md, "
        "upload training scripts/configs/results, or clean up temporary files."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["list", "read", "upload", "delete"], "description": "Operation to perform"},
            "repo_id": {"type": "string", "description": "Repository ID (e.g., 'username/repo-name')"},
            "repo_type": {"type": "string", "enum": ["model", "dataset", "space"], "description": "Repository type (default: model)"},
            "revision": {"type": "string", "description": "Branch/tag/commit (default: main)"},
            "path": {"type": "string", "description": "File path for read/upload"},
            "content": {"type": "string", "description": "File content for upload"},
            "patterns": {"type": "array", "items": {"type": "string"}, "description": "Patterns to delete (e.g., ['*.tmp', 'logs/'])"},
            "create_pr": {"type": "boolean", "description": "Create PR instead of direct commit"},
            "commit_message": {"type": "string", "description": "Custom commit message"},
        },
        "required": ["operation"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        operation = getattr(input_data, "operation", None)
        repo_id = getattr(input_data, "repo_id", None)
        repo_type = getattr(input_data, "repo_type", "model")
        revision = getattr(input_data, "revision", "main")

        if not operation:
            return ToolOutput(success=False, result=None, error="operation is required")
        if not repo_id:
            return ToolOutput(success=False, result=None, error="repo_id is required")

        hf_token = os.environ.get("HF_TOKEN")
        try:
            api = _get_hf_api(hf_token)
        except RuntimeError as e:
            return ToolOutput(success=False, result=None, error=str(e))

        try:
            if operation == "list":
                return await self._list(api, repo_id, repo_type, revision, getattr(input_data, "path", ""))
            elif operation == "read":
                return await self._read(api, repo_id, repo_type, revision, getattr(input_data, "path", ""))
            elif operation == "upload":
                return await self._upload(api, input_data, repo_id, repo_type, revision)
            elif operation == "delete":
                return await self._delete(api, input_data, repo_id, repo_type, revision)
            else:
                return ToolOutput(success=False, result=None, error=f"Unknown operation: {operation}. Valid: list, read, upload, delete")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")

    async def _list(self, api, repo_id: str, repo_type: str, revision: str, path: str) -> ToolOutput:
        items = list(await _async_call(api.list_repo_tree, repo_id=repo_id, repo_type=repo_type, revision=revision, path_in_repo=path, recursive=True))
        if not items:
            return ToolOutput(success=True, result=f"No files in {repo_id}")
        lines = []
        total_size = 0
        for item in sorted(items, key=lambda x: x.path):
            if hasattr(item, "size") and item.size:
                total_size += item.size
                lines.append(f"{item.path} ({_format_size(item.size)})")
            else:
                lines.append(f"{item.path}/")
        url = _build_repo_url(repo_id, repo_type)
        response = f"**{repo_id}** ({len(items)} files, {_format_size(total_size)})\n{url}/tree/{revision}\n\n" + "\n".join(lines)
        return ToolOutput(success=True, result=response)

    async def _read(self, api, repo_id: str, repo_type: str, revision: str, path: str) -> ToolOutput:
        if not path:
            return ToolOutput(success=False, result=None, error="path is required for read")
        from huggingface_hub import hf_hub_download
        file_path = await _async_call(hf_hub_download, repo_id=repo_id, filename=path, repo_type=repo_type, revision=revision, token=api.token)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            truncated = len(content) > 50000
            if truncated:
                content = content[:50000]
            url = f"{_build_repo_url(repo_id, repo_type)}/blob/{revision}/{path}"
            response = f"**{path}**{' (truncated)' if truncated else ''}\n{url}\n\n```\n{content}\n```"
            return ToolOutput(success=True, result=response)
        except UnicodeDecodeError:
            return ToolOutput(success=True, result=f"Binary file at {path}")

    async def _upload(self, api, input_data, repo_id: str, repo_type: str, revision: str) -> ToolOutput:
        path = getattr(input_data, "path", "")
        content = getattr(input_data, "content", "")
        create_pr = getattr(input_data, "create_pr", False)
        commit_message = getattr(input_data, "commit_message", f"Upload {path}")

        if not path:
            return ToolOutput(success=False, result=None, error="path is required for upload")
        if content is None:
            return ToolOutput(success=False, result=None, error="content is required for upload")

        file_bytes = content.encode("utf-8") if isinstance(content, str) else content
        result = await _async_call(
            api.upload_file,
            path_or_fileobj=file_bytes,
            path_in_repo=path,
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
            commit_message=commit_message,
            create_pr=create_pr,
        )
        url = _build_repo_url(repo_id, repo_type)
        if create_pr and hasattr(result, "pr_url"):
            response = f"**Uploaded as PR**\n{result.pr_url}"
        else:
            response = f"**Uploaded:** {path}\n{url}/blob/{revision}/{path}"
        return ToolOutput(success=True, result=response)

    async def _delete(self, api, input_data, repo_id: str, repo_type: str, revision: str) -> ToolOutput:
        patterns = getattr(input_data, "patterns", None)
        create_pr = getattr(input_data, "create_pr", False)
        commit_message = getattr(input_data, "commit_message", f"Delete {', '.join(patterns) if patterns else ''}")

        if not patterns:
            return ToolOutput(success=False, result=None, error="patterns is required for delete")
        if isinstance(patterns, str):
            patterns = [patterns]

        await _async_call(
            api.delete_files,
            repo_id=repo_id,
            delete_patterns=patterns,
            repo_type=repo_type,
            revision=revision,
            commit_message=commit_message,
            create_pr=create_pr,
        )
        return ToolOutput(success=True, result=f"**Deleted:** {', '.join(patterns)} from {repo_id}")


# ---------------------------------------------------------------------------
# hf_repo_git
# ---------------------------------------------------------------------------

class HfRepoGitTool(BaseTool):
    name = "hf_repo_git"
    description = (
        "Git-like operations on HF repos: branches, tags, PRs, and repo management.\n\n"
        "Operations: create_branch, delete_branch, create_tag, delete_tag, list_refs, "
        "create_pr, list_prs, get_pr, merge_pr, close_pr, comment_pr, change_pr_status, "
        "create_repo, update_repo\n\n"
        "PR Workflow: create_pr (draft) → upload with revision='refs/pr/N' → change_pr_status (open) → merge_pr"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["create_branch", "delete_branch", "create_tag", "delete_tag", "list_refs",
                         "create_pr", "list_prs", "get_pr", "merge_pr", "close_pr", "comment_pr",
                         "change_pr_status", "create_repo", "update_repo"],
                "description": "Operation to execute",
            },
            "repo_id": {"type": "string", "description": "Repository ID (e.g., 'username/repo-name')"},
            "repo_type": {"type": "string", "enum": ["model", "dataset", "space"], "description": "Repository type (default: model)"},
            "branch": {"type": "string", "description": "Branch name"},
            "from_rev": {"type": "string", "description": "Create branch from this revision (default: main)"},
            "tag": {"type": "string", "description": "Tag name"},
            "revision": {"type": "string", "description": "Revision for tag (default: main)"},
            "tag_message": {"type": "string", "description": "Tag description"},
            "title": {"type": "string", "description": "PR title"},
            "description": {"type": "string", "description": "PR description"},
            "pr_num": {"type": "integer", "description": "PR/discussion number"},
            "comment": {"type": "string", "description": "Comment text"},
            "status": {"type": "string", "enum": ["open", "closed", "all"], "description": "Filter PRs by status"},
            "new_status": {"type": "string", "enum": ["open", "closed"], "description": "New status for PR"},
            "private": {"type": "boolean", "description": "Make repo private"},
            "gated": {"type": "string", "enum": ["auto", "manual", "false"], "description": "Gated access setting"},
            "space_sdk": {"type": "string", "enum": ["gradio", "streamlit", "docker", "static"], "description": "Space SDK"},
        },
        "required": ["operation"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        operation = getattr(input_data, "operation", None)
        if not operation:
            return ToolOutput(success=False, result=None, error="operation is required")

        repo_id = getattr(input_data, "repo_id", None)
        repo_type = getattr(input_data, "repo_type", "model")
        hf_token = os.environ.get("HF_TOKEN")

        try:
            api = _get_hf_api(hf_token)
        except RuntimeError as e:
            return ToolOutput(success=False, result=None, error=str(e))

        try:
            handler = getattr(self, f"_op_{operation}", None)
            if handler:
                return await handler(api, input_data, repo_id, repo_type)
            else:
                return ToolOutput(success=False, result=None, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolOutput(success=False, result=None, error=f"Error: {e}")

    def _error(self, msg: str) -> ToolOutput:
        return ToolOutput(success=False, result=None, error=msg)

    def _ok(self, msg: str) -> ToolOutput:
        return ToolOutput(success=True, result=msg)

    # Branch operations
    async def _op_create_branch(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        branch = getattr(input_data, "branch", None)
        if not branch:
            return self._error("branch is required")
        from_rev = getattr(input_data, "from_rev", "main")
        await _async_call(api.create_branch, repo_id=repo_id, branch=branch, revision=from_rev, repo_type=repo_type, exist_ok=False)
        url = f"{_build_repo_url(repo_id, repo_type)}/tree/{branch}"
        return self._ok(f"**Branch created:** {branch}\n{url}")

    async def _op_delete_branch(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        branch = getattr(input_data, "branch", None)
        if not branch:
            return self._error("branch is required")
        await _async_call(api.delete_branch, repo_id=repo_id, branch=branch, repo_type=repo_type)
        return self._ok(f"**Branch deleted:** {branch}")

    # Tag operations
    async def _op_create_tag(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        tag = getattr(input_data, "tag", None)
        if not tag:
            return self._error("tag is required")
        revision = getattr(input_data, "revision", "main")
        tag_message = getattr(input_data, "tag_message", "")
        await _async_call(api.create_tag, repo_id=repo_id, tag=tag, revision=revision, tag_message=tag_message, repo_type=repo_type, exist_ok=False)
        url = f"{_build_repo_url(repo_id, repo_type)}/tree/{tag}"
        return self._ok(f"**Tag created:** {tag}\n{url}")

    async def _op_delete_tag(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        tag = getattr(input_data, "tag", None)
        if not tag:
            return self._error("tag is required")
        await _async_call(api.delete_tag, repo_id=repo_id, tag=tag, repo_type=repo_type)
        return self._ok(f"**Tag deleted:** {tag}")

    async def _op_list_refs(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        refs = await _async_call(api.list_repo_refs, repo_id=repo_id, repo_type=repo_type)
        branches = [b.name for b in refs.branches] if refs.branches else []
        tags = [t.name for t in refs.tags] if hasattr(refs, "tags") and refs.tags else []
        url = _build_repo_url(repo_id, repo_type)
        lines = [f"**{repo_id}**", url, ""]
        lines.append(f"**Branches ({len(branches)}):** " + ", ".join(branches) if branches else "**Branches:** none")
        lines.append(f"**Tags ({len(tags)}):** " + ", ".join(tags) if tags else "**Tags:** none")
        return self._ok("\n".join(lines))

    # PR operations
    async def _op_create_pr(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        title = getattr(input_data, "title", None)
        if not title:
            return self._error("title is required")
        description = getattr(input_data, "description", "")
        result = await _async_call(api.create_pull_request, repo_id=repo_id, title=title, description=description, repo_type=repo_type)
        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{result.num}"
        return self._ok(f'**Draft PR #{result.num} created:** {title}\n{url}\n\nAdd commits via upload with revision="refs/pr/{result.num}"')

    async def _op_list_prs(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        status = getattr(input_data, "status", "all")
        discussions = list(api.get_repo_discussions(repo_id=repo_id, repo_type=repo_type, discussion_status=status if status != "all" else None))
        if not discussions:
            return self._ok(f"No discussions in {repo_id}")
        url = _build_repo_url(repo_id, repo_type)
        lines = [f"**{repo_id}** - {len(discussions)} discussions", f"{url}/discussions", ""]
        for d in discussions[:20]:
            status_label = {"draft": "[DRAFT]", "open": "[OPEN]", "merged": "[MERGED]"}.get(d.status, "[CLOSED]")
            type_label = "PR" if d.is_pull_request else "D"
            lines.append(f"{status_label} #{d.num} [{type_label}] {d.title}")
        return self._ok("\n".join(lines))

    async def _op_get_pr(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        pr_num = getattr(input_data, "pr_num", None)
        if not pr_num:
            return self._error("pr_num is required")
        pr = await _async_call(api.get_discussion_details, repo_id=repo_id, discussion_num=int(pr_num), repo_type=repo_type)
        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        status_map = {"draft": "Draft", "open": "Open", "merged": "Merged", "closed": "Closed"}
        status = status_map.get(pr.status, pr.status.capitalize())
        type_label = "Pull Request" if pr.is_pull_request else "Discussion"
        lines = [f"**{type_label} #{pr_num}:** {pr.title}", f"**Status:** {status}", f"**Author:** {pr.author}", url]
        return self._ok("\n".join(lines))

    async def _op_merge_pr(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        pr_num = getattr(input_data, "pr_num", None)
        if not pr_num:
            return self._error("pr_num is required")
        comment = getattr(input_data, "comment", "")
        await _async_call(api.merge_pull_request, repo_id=repo_id, discussion_num=int(pr_num), comment=comment, repo_type=repo_type)
        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        return self._ok(f"**PR #{pr_num} merged**\n{url}")

    async def _op_close_pr(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        pr_num = getattr(input_data, "pr_num", None)
        if not pr_num:
            return self._error("pr_num is required")
        comment = getattr(input_data, "comment", "")
        await _async_call(api.change_discussion_status, repo_id=repo_id, discussion_num=int(pr_num), new_status="closed", comment=comment, repo_type=repo_type)
        return self._ok(f"**Discussion #{pr_num} closed**")

    async def _op_comment_pr(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        pr_num = getattr(input_data, "pr_num", None)
        comment = getattr(input_data, "comment", None)
        if not pr_num:
            return self._error("pr_num is required")
        if not comment:
            return self._error("comment is required")
        await _async_call(api.comment_discussion, repo_id=repo_id, discussion_num=int(pr_num), comment=comment, repo_type=repo_type)
        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        return self._ok(f"**Comment added to #{pr_num}**\n{url}")

    async def _op_change_pr_status(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        pr_num = getattr(input_data, "pr_num", None)
        new_status = getattr(input_data, "new_status", None)
        if not pr_num:
            return self._error("pr_num is required")
        if not new_status:
            return self._error("new_status is required (open or closed)")
        comment = getattr(input_data, "comment", "")
        await _async_call(api.change_discussion_status, repo_id=repo_id, discussion_num=int(pr_num), new_status=new_status, comment=comment, repo_type=repo_type)
        url = f"{_build_repo_url(repo_id, repo_type)}/discussions/{pr_num}"
        return self._ok(f"**PR #{pr_num} status changed to {new_status}**\n{url}")

    # Repo management
    async def _op_create_repo(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        private = getattr(input_data, "private", True)
        space_sdk = getattr(input_data, "space_sdk", None)
        if repo_type == "space" and not space_sdk:
            return self._error("space_sdk required for spaces (gradio/streamlit/docker/static)")
        kwargs = {"repo_id": repo_id, "repo_type": repo_type, "private": private, "exist_ok": False}
        if space_sdk:
            kwargs["space_sdk"] = space_sdk
        result = await _async_call(api.create_repo, **kwargs)
        return self._ok(f"**Repository created:** {repo_id}\n**Private:** {private}\n{result}")

    async def _op_update_repo(self, api, input_data, repo_id, repo_type) -> ToolOutput:
        if not repo_id:
            return self._error("repo_id is required")
        private = getattr(input_data, "private", None)
        gated = getattr(input_data, "gated", None)
        if private is None and gated is None:
            return self._error("Specify private (bool) or gated ('auto'/'manual'/false)")
        kwargs = {"repo_id": repo_id, "repo_type": repo_type}
        if private is not None:
            kwargs["private"] = private
        if gated is not None:
            kwargs["gated"] = gated
        await _async_call(api.update_repo_settings, **kwargs)
        changes = []
        if private is not None:
            changes.append(f"private={private}")
        if gated is not None:
            changes.append(f"gated={gated}")
        url = f"{_build_repo_url(repo_id, repo_type)}/settings"
        return self._ok(f"**Settings updated:** {', '.join(changes)}\n{url}")
