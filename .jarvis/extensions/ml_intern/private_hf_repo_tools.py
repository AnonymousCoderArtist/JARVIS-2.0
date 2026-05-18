"""Private HF Repos Tool - Manage private Hugging Face repositories

PRIMARY USE: Store job outputs, training scripts, and logs from HF Jobs.
Since job results are ephemeral, this tool provides persistent storage in private repos.
"""

import asyncio
from typing import Any, Dict, Literal, Optional

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import HfHubHTTPError

from .types import ToolResult

OperationType = Literal[
    "upload_file", "create_repo", "check_repo", "list_files", "read_file"
]


async def _async_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _build_repo_url(repo_id: str, repo_type: str = "dataset") -> str:
    type_path = "" if repo_type == "model" else f"{repo_type}s"
    return f"https://huggingface.co/{type_path}/{repo_id}".replace("//", "/")


def _content_to_bytes(content: str | bytes) -> bytes:
    if isinstance(content, str):
        return content.encode("utf-8")
    return content


class PrivateHfRepoTool:
    """Tool for managing private Hugging Face repositories."""

    def __init__(self, hf_token: Optional[str] = None):
        self.api = HfApi(token=hf_token)

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        operation = params.get("operation")
        args = params.get("args", {})

        if not operation:
            return self._show_help()

        operation = operation.lower()

        if args.get("help"):
            return self._show_operation_help(operation)

        try:
            if operation == "upload_file":
                return await self._upload_file(args)
            elif operation == "create_repo":
                return await self._create_repo(args)
            elif operation == "check_repo":
                return await self._check_repo(args)
            elif operation == "list_files":
                return await self._list_files(args)
            elif operation == "read_file":
                return await self._read_file(args)
            else:
                return {
                    "formatted": f'Unknown operation: "{operation}"\n\nAvailable: upload_file, create_repo, check_repo, list_files, read_file',
                    "totalResults": 0,
                    "resultsShared": 0,
                    "isError": True,
                }

        except HfHubHTTPError as e:
            return {
                "formatted": f"API Error: {str(e)}",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }
        except Exception as e:
            return {
                "formatted": f"Error executing {operation}: {str(e)}",
                "totalResults": 0,
                "resultsShared": 0,
                "isError": True,
            }

    def _show_help(self) -> ToolResult:
        return {
            "formatted": """# Private HF Repos Tool

PRIMARY USE: Store job outputs, scripts, and logs from HF Jobs to private repos.

Available: upload_file, create_repo, check_repo, list_files, read_file

Write ops: file_content, path_in_repo, repo_id, repo_type (dataset/model/space),
           create_if_missing (bool), commit_message, space_sdk

Read ops: repo_id, path_in_repo, repo_type

Repos always created as private. Spaces need space_sdk.""",
            "totalResults": 1,
            "resultsShared": 1,
        }

    def _show_operation_help(self, operation: str) -> ToolResult:
        return {
            "formatted": f"Help for operation: {operation}\n\nCall with appropriate arguments.",
            "totalResults": 1,
            "resultsShared": 1,
        }

    async def _upload_file(self, args: Dict[str, Any]) -> ToolResult:
        file_content = args.get("file_content")
        path_in_repo = args.get("path_in_repo")
        repo_id = args.get("repo_id")

        if not file_content:
            return self._error("file_content is required")
        if not path_in_repo:
            return self._error("path_in_repo is required")
        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "dataset")
        create_if_missing = args.get("create_if_missing", False)

        try:
            repo_exists = await _async_call(
                self.api.repo_exists, repo_id=repo_id, repo_type=repo_type
            )

            if not repo_exists and create_if_missing:
                create_args = {
                    "repo_id": repo_id,
                    "repo_type": repo_type,
                    "private": True,
                }
                if "space_sdk" in args:
                    create_args["space_sdk"] = args["space_sdk"]
                await self._create_repo(create_args)
            elif not repo_exists:
                return self._error(
                    f"Repository {repo_id} does not exist. Set create_if_missing: true to create it."
                )

        except Exception as e:
            return self._error(f"Failed to check repository: {str(e)}")

        file_bytes = _content_to_bytes(file_content)

        try:
            await _async_call(
                self.api.upload_file,
                path_or_fileobj=file_bytes,
                path_in_repo=path_in_repo,
                repo_id=repo_id,
                repo_type=repo_type,
                commit_message=args.get("commit_message", f"Upload {path_in_repo}"),
            )

            repo_url = _build_repo_url(repo_id, repo_type)
            file_url = f"{repo_url}/blob/main/{path_in_repo}"

            return {
                "formatted": f"✓ File uploaded!\n**Repo:** {repo_id}\n**File:** {path_in_repo}\n**View:** {file_url}",
                "totalResults": 1,
                "resultsShared": 1,
            }

        except Exception as e:
            return self._error(f"Failed to upload file: {str(e)}")

    async def _create_repo(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "dataset")
        private = True
        space_sdk = args.get("space_sdk")

        try:
            repo_exists = await _async_call(
                self.api.repo_exists, repo_id=repo_id, repo_type=repo_type
            )

            if repo_exists:
                repo_url = _build_repo_url(repo_id, repo_type)
                return {
                    "formatted": f"Repository {repo_id} already exists.\n**View at:** {repo_url}",
                    "totalResults": 1,
                    "resultsShared": 1,
                }

            if repo_type == "space" and not space_sdk:
                return self._error(
                    "space_sdk required for spaces (gradio/streamlit/static/docker)"
                )

            kwargs = {
                "repo_id": repo_id,
                "repo_type": repo_type,
                "private": private,
                "exist_ok": True,
            }
            if repo_type == "space" and space_sdk:
                kwargs["space_sdk"] = space_sdk

            repo_url = await _async_call(self.api.create_repo, **kwargs)

            return {
                "formatted": f"✓ Repository created!\n**Repo:** {repo_id}\n**Type:** {repo_type}\n**Private:** Yes\n**View:** {repo_url}",
                "totalResults": 1,
                "resultsShared": 1,
            }

        except Exception as e:
            return self._error(f"Failed to create repository: {str(e)}")

    async def _check_repo(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "dataset")

        try:
            repo_exists = await _async_call(
                self.api.repo_exists, repo_id=repo_id, repo_type=repo_type
            )

            if repo_exists:
                repo_url = _build_repo_url(repo_id, repo_type)
                return {
                    "formatted": f"✓ Repository exists!\n**Repo:** {repo_id}\n**Type:** {repo_type}\n**View:** {repo_url}",
                    "totalResults": 1,
                    "resultsShared": 1,
                }
            else:
                return {
                    "formatted": f"Repository does not exist: {repo_id}",
                    "totalResults": 0,
                    "resultsShared": 0,
                }

        except Exception as e:
            return self._error(f"Failed to check repository: {str(e)}")

    async def _list_files(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")

        if not repo_id:
            return self._error("repo_id is required")

        repo_type = args.get("repo_type", "dataset")

        try:
            files = await _async_call(
                self.api.list_repo_files, repo_id=repo_id, repo_type=repo_type
            )

            if not files:
                return {
                    "formatted": f"No files found in: {repo_id}",
                    "totalResults": 0,
                    "resultsShared": 0,
                }

            repo_url = _build_repo_url(repo_id, repo_type)
            return {
                "formatted": f"**Files in {repo_id}** ({len(files)} total)\n{repo_url}\n\n" + "\n".join(f"- {f}" for f in sorted(files)),
                "totalResults": len(files),
                "resultsShared": len(files),
            }

        except Exception as e:
            return self._error(f"Failed to list files: {str(e)}")

    async def _read_file(self, args: Dict[str, Any]) -> ToolResult:
        repo_id = args.get("repo_id")
        path_in_repo = args.get("path_in_repo")

        if not repo_id:
            return self._error("repo_id is required")
        if not path_in_repo:
            return self._error("path_in_repo is required")

        repo_type = args.get("repo_type", "dataset")

        try:
            file_path = await _async_call(
                hf_hub_download,
                repo_id=repo_id,
                filename=path_in_repo,
                repo_type=repo_type,
                token=self.api.token,
            )

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            repo_url = _build_repo_url(repo_id, repo_type)
            return {
                "formatted": f"**{path_in_repo}** ({len(content)} chars)\n{repo_url}/blob/main/{path_in_repo}\n\n```\n{content}\n```",
                "totalResults": 1,
                "resultsShared": 1,
            }

        except UnicodeDecodeError:
            try:
                with open(file_path, "rb") as f:
                    binary_content = f.read()
                return {
                    "formatted": f"Binary file ({len(binary_content)} bytes). Cannot display as text.",
                    "totalResults": 1,
                    "resultsShared": 1,
                }
            except Exception as e:
                return self._error(f"Failed to read binary file: {str(e)}")
        except Exception as e:
            return self._error(f"Failed to read file: {str(e)}")

    def _error(self, message: str) -> ToolResult:
        return {
            "formatted": message,
            "totalResults": 0,
            "resultsShared": 0,
            "isError": True,
        }


PRIVATE_HF_REPO_TOOL_SPEC = {
    "name": "hf_private_repos",
    "description": (
        "Manage private HF repositories - create, upload, read, list files in models/datasets/spaces. "
        "⚠️ PRIMARY USE: Store job outputs persistently (job storage is ephemeral). "
        "Operations: create_repo, upload_file, read_file, list_files, check_repo. "
        "ALWAYS pass file_content as string (not file paths). Repos are ALWAYS private by default. "
        "For Spaces: must provide space_sdk (gradio/streamlit/static/docker)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["upload_file", "create_repo", "check_repo", "list_files", "read_file"],
            },
            "args": {
                "type": "object",
                "additionalProperties": True,
            },
        },
    },
}


async def private_hf_repo_handler(arguments: Dict[str, Any]) -> tuple[str, bool]:
    try:
        tool = PrivateHfRepoTool()
        result = await tool.execute(arguments)
        return result["formatted"], not result.get("isError", False)
    except Exception as e:
        return f"Error executing Private HF Repo tool: {str(e)}", False
