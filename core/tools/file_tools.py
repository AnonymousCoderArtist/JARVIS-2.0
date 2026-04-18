"""File operation tools"""

import os

import aiofiles

from .base import BaseTool, ToolInput, ToolOutput


class FileReadTool(BaseTool):
    """Tool for reading file contents (Copilot Chat style)"""

    name = "file_read"
    description = "Read the contents of a file. Line numbers are 1-indexed. This tool will truncate its output at 2000 lines and may be called repeatedly with offset and limit parameters to read larger files in chunks."
    input_schema = {
        "type": "object",
        "properties": {
            "filePath": {
                "type": "string",
                "description": "The absolute path of the file to read",
                "minLength": 1
            },
            "offset": {
                "type": "integer",
                "description": "Optional: the 1-based line number to start reading from. Only use this if the file is too large to read at once. If not specified, the file will be read from the beginning.",
                "minimum": 1
            },
            "limit": {
                "type": "integer",
                "description": "Optional: the maximum number of lines to read. Only use this together with offset if the file is too large to read at once.",
                "minimum": 1
            },
            "encoding": {
                "type": "string",
                "description": "Character encoding for reading the file",
                "default": "utf-8",
                "examples": ["utf-8", "latin-1", "ascii"]
            }
        },
        "required": ["filePath"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            file_path = getattr(input_data, "filePath", None)
            offset = getattr(input_data, "offset", None)
            limit = getattr(input_data, "limit", None)
            encoding = getattr(input_data, "encoding", "utf-8")

            if not isinstance(file_path, str) or not file_path:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid file path"
                )

            if offset is not None and not isinstance(offset, int):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid offset"
                )

            if limit is not None and not isinstance(limit, int):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid limit"
                )

            if not isinstance(encoding, str):
                encoding = "utf-8"

            if not os.path.exists(file_path):
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"File not found: {file_path}"
                )

            async with aiofiles.open(file_path, encoding=encoding) as f:
                lines = await f.readlines()
                total_lines = len(lines)

                # Apply offset and limit (1-indexed to 0-indexed)
                start_idx = (offset - 1) if offset is not None else 0
                if limit is not None:
                    end_idx = start_idx + limit
                else:
                    end_idx = len(lines)

                # Truncate at 2000 lines like Copilot Chat
                if end_idx - start_idx > 2000:
                    end_idx = start_idx + 2000

                # Ensure indices are within bounds
                start_idx = max(0, min(start_idx, total_lines))
                end_idx = max(0, min(end_idx, total_lines))

                content = "".join(lines[start_idx:end_idx])

                metadata = {
                    "filePath": file_path,
                    "size": len(content),
                    "total_lines": total_lines,
                    "lines_returned": end_idx - start_idx
                }

                if offset is not None:
                    metadata["offset"] = offset
                if limit is not None:
                    metadata["limit"] = limit
                if end_idx < total_lines:
                    metadata["truncated"] = True

            return ToolOutput(
                success=True,
                result=content,
                metadata=metadata
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to read file: {str(e)}"
            )


class FileWriteTool(BaseTool):
    """Tool for writing content to files (Copilot Chat style)"""

    name = "create_file"
    description = "This is a tool for creating a new file in the workspace. The file will be created with the specified content. The directory will be created if it does not already exist. Never use this tool to edit a file that already exists."
    input_schema = {
        "type": "object",
        "properties": {
            "filePath": {
                "type": "string",
                "description": "The absolute path to the file to create",
                "minLength": 1
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file"
            }
        },
        "required": ["filePath", "content"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            file_path = getattr(input_data, "filePath", None)
            content = getattr(input_data, "content", None)

            if not isinstance(file_path, str) or not file_path:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid file path"
                )

            if not isinstance(content, str):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid file content"
                )

            # Check if file already exists
            if os.path.exists(file_path):
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"File already exists: {file_path}. Use the replace tool to edit existing files."
                )

            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(content)

            return ToolOutput(
                success=True,
                result=f"Successfully created file: {file_path}",
                metadata={"filePath": file_path, "size": len(content)}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to create file: {str(e)}"
            )


class ListDirectoryTool(BaseTool):
    """Tool for listing directory contents (Copilot Chat style)"""

    name = "list_dir"
    description = "List the contents of a directory. Result will have the name of the child. If the name ends in /, it's a folder, otherwise a file"
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute path to the directory to list",
                "minLength": 1
            }
        },
        "required": ["path"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            path = getattr(input_data, "path", None)

            if not isinstance(path, str) or not path:
                return ToolOutput(success=False, result=None, error="Invalid directory path")

            if not os.path.exists(path):
                return ToolOutput(success=False, result=None, error=f"Directory not found: {path}")

            if not os.path.isdir(path):
                return ToolOutput(success=False, result=None, error=f"Path is not a directory: {path}")

            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                # If name ends with /, it's a folder, otherwise a file (Copilot Chat convention)
                name_with_suffix = item + "/" if os.path.isdir(item_path) else item
                items.append(name_with_suffix)

            return ToolOutput(
                success=True,
                result=items,
                metadata={"path": path, "count": len(items)}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to list directory: {str(e)}"
            )


class GlobTool(BaseTool):
    """Tool for searching files by pattern (Copilot Chat style)"""

    name = "file_search"
    description = "Search for files in the workspace by glob pattern. This only returns the paths of matching files. Use this tool when you know the exact filename pattern of the files you're searching for. Glob patterns match from the root of the workspace folder. Examples: **/*.{js,ts} to match all js/ts files in the workspace. src/** to match all files under the top-level src folder. **/foo/**/*.js to match all js files under any foo folder in the workspace."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search for files with names or paths matching this glob pattern",
                "minLength": 1
            },
            "maxResults": {
                "type": "integer",
                "description": "The maximum number of results to return. Do not use this unless necessary, it can slow things down. By default, only some matches are returned. If you use this and don't see what you're looking for, you can try again with a more specific query or a larger maxResults.",
                "minimum": 1
            }
        },
        "required": ["query"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            query = getattr(input_data, "query", None)
            max_results = getattr(input_data, "maxResults", None)

            if not isinstance(query, str) or not query:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid glob query"
                )

            if max_results is not None and not isinstance(max_results, int):
                max_results = 0

            import glob

            # Search from current working directory (workspace root)
            matches = glob.glob(query, recursive=True)

            # Apply maxResults limit
            if max_results and max_results > 0:
                matches = matches[:max_results]

            return ToolOutput(
                success=True,
                result=matches,
                metadata={"query": query, "count": len(matches)}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to search files: {str(e)}"
            )
