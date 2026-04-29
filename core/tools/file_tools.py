"""File operation tools"""

import os

import aiofiles

from .base import BaseTool, ToolInput, ToolOutput


class FileReadTool(BaseTool):
    """Tool for reading file contents (OpenClaude style)"""

    name = "file_read"
    description = """Read a file from the local filesystem. You can access any file directly by using this tool. Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- When you already know which part of the file you need, only read that part. This can be important for larger files.
- Results are returned using cat -n format, with line numbers starting at 1
- This tool allows reading images (eg PNG, JPG, etc). When reading an image file the contents are presented visually.
- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, combining code, text, and visualizations.
- This tool can only read files, not directories. To read a directory, use an ls command via the bash tool.
- You will regularly be asked to read screenshots. If the user provides a path to a screenshot, ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents."""
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
                    error="Invalid file path: file_path parameter must be a non-empty string. Please provide a valid absolute file path."
                )

            if offset is not None and not isinstance(offset, int):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid offset: offset parameter must be a positive integer. Please provide a valid line number to start reading from."
                )

            if limit is not None and not isinstance(limit, int):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid limit: limit parameter must be a positive integer. Please provide a valid maximum number of lines to read."
                )

            if not isinstance(encoding, str):
                encoding = "utf-8"

            if not os.path.exists(file_path):
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"File not found: {file_path}. Please verify the file path is correct and the file exists. Use list_directory or glob to find the correct file path."
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
                error=f"Failed to read file: {str(e)}. Please check if the file exists, you have permission to read it, and the path is correct. Use list_directory to verify the file location."
            )


class FileWriteTool(BaseTool):
    """Tool for writing content to files (OpenClaude style)"""

    name = "create_file"
    description = """Create a new file in the workspace with the specified content. The directory will be created if it does not already exist.

IMPORTANT: Never use this tool to edit a file that already exists. Use the replace tool for editing existing files.

Usage:
- The filePath parameter must be an absolute path, not a relative path
- The content parameter should contain the full file contents
- Parent directories will be created automatically if they don't exist
- This tool will fail if the file already exists (use replace tool instead)
- Use this tool only when creating new files from scratch"""
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
                    error="Invalid file path: file_path parameter must be a non-empty string. Please provide a valid absolute file path."
                )

            if not isinstance(content, str):
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid file content: content parameter must be a string. Please provide the file content as a string."
                )

            # Check if file already exists
            if os.path.exists(file_path):
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"File already exists: {file_path}. To edit an existing file, use the replace tool instead. The create_file tool is only for creating new files."
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
                error=f"Failed to create file: {str(e)}. Please check if you have permission to create files in the directory and if the parent directory path is valid."
            )


class ListDirectoryTool(BaseTool):
    """Tool for listing directory contents (OpenClaude style)"""

    name = "list_dir"
    description = """List the contents of a directory. Result will have the name of the child. If the name ends in /, it's a folder, otherwise a file.

Usage:
- The path parameter must be an absolute path to the directory
- Returns a list of item names with / suffix for directories
- Use this to understand the structure of a directory
- Useful for exploring project structure and finding files"""
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
                return ToolOutput(success=False, result=None, error="Invalid directory path: path parameter must be a non-empty string. Please provide a valid absolute directory path.")

            if not os.path.exists(path):
                return ToolOutput(success=False, result=None, error=f"Directory not found: {path}. Please verify the directory path is correct and exists. Use glob to search for directories if you're unsure of the exact path.")

            if not os.path.isdir(path):
                return ToolOutput(success=False, result=None, error=f"Path is not a directory: {path}. The provided path exists but is a file, not a directory. Please provide a directory path or use file_read to read this file.")

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
                error=f"Failed to list directory: {str(e)}. Please check if you have permission to access this directory and if the path is valid."
            )


class GlobTool(BaseTool):
    """Tool for searching files by pattern (OpenClaude style)"""

    name = "file_search"
    description = """Search for files in the workspace by glob pattern. This only returns the paths of matching files. Use this tool when you know the exact filename pattern of the files you're searching for.

Usage:
- Glob patterns match from the root of the workspace folder
- Examples:
  - **/*.{js,ts} to match all js/ts files in the workspace
  - src/** to match all files under the top-level src folder
  - **/foo/**/*.js to match all js files under any foo folder in the workspace
  - **/*.py to match all Python files recursively
- Use maxResults parameter to limit the number of results if needed
- This tool is faster than grep for finding files by name pattern
- Use grep_search instead when searching for content within files"""
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
                    error="Invalid glob query: query parameter must be a non-empty string. Please provide a valid glob pattern (e.g., '**/*.py' or 'src/**')"
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
                error=f"Failed to search files: {str(e)}. Please check if your glob pattern is valid and if you have permission to access the search directories."
            )
