"""File operation tools"""

import os
from typing import Any

import aiofiles

from .base import BaseTool, ToolInput, ToolOutput
from core.tools.permissions import (
    PermissionContext,
    PermissionScope,
    RequiredPermission,
    is_path_within_workdir,
    resolve_path_permission,
    resolve_file_tool_permission,
    ToolPermission,
)


class FileReadTool(BaseTool):
    """Tool for reading file contents - uses files array format"""

    name = "read"
    description = """Read file(s) from the local filesystem. Supports both single file and multiple files formats.

**USAGE - Single File (backward compatible):**
```json
{
  "filePath": "/absolute/path/to/file.py",
  "offset": 1,
  "limit": 10,
  "encoding": "utf-8"
}
```

**USAGE - Multiple Files:**
```json
{
  "files": [
    {"file_path": "/absolute/path/to/file.py", "offset": 1, "limit": 10},
    {"file_path": "/absolute/path/to/file2.py", "offset": 10, "limit": 10}
  ],
  "encoding": "utf-8"
}
```

**PARAMETERS - Single File Mode:**
- `filePath`: Absolute path to the file to read (required)
- `offset`: 1-based line number to start reading from (optional, default: 1, minimum: 1)
- `limit`: Maximum number of lines to read (optional, default: 10, minimum: 1, maximum: 1000)
- `encoding`: Character encoding for reading files (optional, default: "utf-8")

**PARAMETERS - Multiple Files Mode:**
- `files`: Array of file objects (required)
  - `file_path`: Absolute path to the file to read (required)
  - `offset`: 1-based line number to start reading from (required, minimum: 1)
  - `limit`: Maximum number of lines to read (required, minimum: 1, maximum: 1000)
- `encoding`: Character encoding for reading files (optional, default: "utf-8")

**BEHAVIOR:**
- Returns concatenated content with `--- {file_path} ---` separators between files (multiple files mode)
- Returns content with metadata including file path (single file mode)
- Files are read in parallel for performance (multiple files mode)
- Each file respects individual offset/limit settings
- Read errors for individual files are reported but don't fail the entire operation
- Supports reading text files with various encodings
- Lines longer than 2000 characters are truncated

**EXAMPLES:**
- Single file, first 10 lines: `{"filePath": "/path/to/file.py", "offset": 1, "limit": 10}`
- Single file, lines 20-30: `{"filePath": "/path/to/file.py", "offset": 20, "limit": 11}`
- Multiple files: `{"files": [{"file_path": "/path/file1.py", "offset": 1, "limit": 5}, {"file_path": "/path/file2.py", "offset": 1, "limit": 5}]}`"""

    input_schema = {
        "type": "object",
        "properties": {
            # Single file mode parameters
            "filePath": {
                "type": "string",
                "description": "Absolute path to the file to read (single file mode)"
            },
            "offset": {
                "type": "integer",
                "description": "1-based line number to start reading from (single file mode)",
                "minimum": 1,
                "default": 1
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (single file mode, maximum: 1000)",
                "minimum": 1,
                "maximum": 1000,
                "default": 10
            },
            # Multiple files mode parameters
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the file to read"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "1-based line number to start reading from",
                            "minimum": 1,
                            "default": 1
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of lines to read (maximum: 1000)",
                            "minimum": 1,
                            "maximum": 1000,
                            "default": 10
                        }
                    },
                    "required": ["file_path", "offset", "limit"]
                },
                "minItems": 1,
                "description": "Array of file objects with file_path, offset, and limit (multiple files mode)"
            },
            "encoding": {
                "type": "string",
                "description": "Character encoding for reading files",
                "default": "utf-8",
                "examples": ["utf-8", "latin-1", "ascii"]
            }
        },
        "oneOf": [
            {"required": ["filePath"]},
            {"required": ["files"]}
        ]
    }

    def resolve_permission(self, args: dict) -> PermissionContext | None:
        """Resolve permission for file read operation with granular checks"""
        files = args.get("files", [])
        
        # Handle case where files is not a list (e.g., passed as string)
        if not isinstance(files, list):
            return None
        
        if files and len(files) > 0:
            first_file = files[0]
            file_path = first_file.get("file_path") if isinstance(first_file, dict) else None
        else:
            file_path = None
        
        if not file_path:
            return None

        # Get configuration
        from core.config.settings import Settings
        settings = Settings()
        allowlist = settings.tools.get("allowlist", [])
        denylist = settings.tools.get("denylist", [])
        sensitive_patterns = settings.tools.get("sensitive_patterns", [])
        config_permission = ToolPermission(
            settings.tools.get("read", {}).get("permission", "ask")
        )

        return resolve_file_tool_permission(
            file_path,
            tool_name="read",
            allowlist=allowlist,
            denylist=denylist,
            config_permission=config_permission,
            sensitive_patterns=sensitive_patterns,
        )

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names (camelCase and snake_case)"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case parameter names
            files = self._get_param(input_data, "files", "files")
            encoding = self._get_param(input_data, "encoding") or "utf-8"

            # Normalize encoding
            if not isinstance(encoding, str):
                encoding = "utf-8"

            # Check if using new files array format
            if files is not None:
                if not isinstance(files, list):
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="Invalid files format: expected a list of file objects with file_path, offset, and limit fields"
                    )

                if len(files) == 0:
                    return ToolOutput(
                        success=False,
                        result=None,
                        error="No files provided. Use the 'files' array with at least one file object containing 'file_path', 'offset', and 'limit'."
                    )

                return await self._execute_files_array(files, encoding)

            # Backward compatibility: check for single file parameters
            file_path = self._get_param(input_data, "filePath", "file_path")
            offset = self._get_param(input_data, "offset")
            limit = self._get_param(input_data, "limit")

            if file_path is None:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="No file path provided. Use either 'filePath' for single file or 'files' array for multiple files."
                )

            # For single file mode, offset and limit are required (not optional with defaults)
            if offset is None:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Missing required parameter 'offset' for single file mode."
                )

            if limit is None:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Missing required parameter 'limit' for single file mode."
                )

            # Convert to files array format for processing
            files_array = [{
                "file_path": file_path,
                "offset": offset,
                "limit": limit
            }]

            # Execute and convert result to single file format
            array_result = await self._execute_files_array(files_array, encoding)
            if not array_result.success:
                return array_result

            # Convert to single file metadata format
            result_content = array_result.result
            if result_content and result_content.startswith(f"--- {file_path} ---\n"):
                result_content = result_content[len(f"--- {file_path} ---\n"):]

            metadata = {
                "filePath": file_path,
                "offset": offset,
                "lines": len(result_content.split('\n')) if result_content else 0
            }

            return ToolOutput(
                success=True,
                result=result_content,
                metadata=metadata
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to read files: {str(e)}. Please check if the files exist, you have permission to read them, and the paths are correct."
            )

    async def _execute_files_array(self, files: list, encoding: str) -> ToolOutput:
        """Execute reading multiple files with individual options (similar to edit's replacements array)"""
        import asyncio

        processed_files = []
        skipped_files = []
        contents = []

        async def read_single_file(file_obj, index: int) -> tuple | None:
            try:
                # Validate file_obj is a dict
                if not isinstance(file_obj, dict):
                    return (None, None, f"File {index + 1}: Invalid format - expected a dict with file_path, offset, and limit, got {type(file_obj).__name__}", None, None)
                
                fp = file_obj.get("file_path")
                off = file_obj.get("offset")
                lim = file_obj.get("limit")

                if not isinstance(fp, str) or not fp:
                    return (None, None, f"File {index + 1}: Missing or invalid file_path", None, None)

                if not os.path.exists(fp):
                    return (None, None, f"File {index + 1}: File not found: {fp}", None, None)

                async with aiofiles.open(fp, encoding=encoding) as f:
                    lines = await f.readlines()
                total_lines = len(lines)

                # Apply offset (default 1) and limit
                start_idx = (off - 1) if off is not None and isinstance(off, int) and off > 0 else 0
                if lim is not None:
                    if not isinstance(lim, int) or lim < 1:
                        lim = 10
                    end_idx = start_idx + lim
                else:
                    end_idx = total_lines

                # Cap at 1000 lines to prevent abuse
                if end_idx - start_idx > 1000:
                    end_idx = start_idx + 1000

                start_idx = max(0, min(start_idx, total_lines))
                end_idx = max(0, min(end_idx, total_lines))

                content = "".join(lines[start_idx:end_idx])

                return (fp, content, None, start_idx + 1, end_idx - start_idx)
            except Exception as e:
                return (None, None, f"File {index + 1}: {str(e)}", None, None)

        # Run all reads in parallel
        results = await asyncio.gather(*[read_single_file(f, i) for i, f in enumerate(files)])

        for result in results:
            if result is None:
                continue
            file_path, content, error, offset_used, lines_returned = result
            if content is not None:
                contents.append(f"--- {file_path} ---\n{content}")
                processed_files.append({"file": file_path, "offset": offset_used, "lines": lines_returned})
            if error:
                skipped_files.append({"path": file_path or "unknown", "reason": error})

        if not contents:
            return ToolOutput(
                success=False,
                result=None,
                error=f"No files could be read. Skipped files: {skipped_files}"
            )

        concatenated = "\n".join(contents)
        metadata = {
            "processed_files": processed_files,
            "skipped_files": skipped_files,
            "total_files_processed": len(processed_files),
            "total_files_skipped": len(skipped_files),
        }

        return ToolOutput(
            success=True,
            result=concatenated,
            metadata=metadata
        )

    
    

class FileWriteTool(BaseTool):
    """Tool for writing content to files (OpenClaude style)"""

    name = "write"
    description = """Create a new file in the workspace with the specified content. The directory will be created if it does not already exist.

IMPORTANT: Use the parameter name 'filePath' (camelCase) when calling this tool.

- This tool will fail if the file already exists (use edit tool instead)
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

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names (camelCase and snake_case)"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    def resolve_permission(self, args: dict) -> PermissionContext | None:
        """Resolve permission for file write operation with granular checks"""
        file_path = args.get("filePath")
        if not file_path:
            return None

        # Get configuration
        from core.config.settings import Settings
        settings = Settings()
        allowlist = settings.tools.get("allowlist", [])
        denylist = settings.tools.get("denylist", [])
        sensitive_patterns = settings.tools.get("sensitive_patterns", [])
        config_permission = ToolPermission(
            settings.tools.get("write", {}).get("permission", "ask")
        )

        return resolve_file_tool_permission(
            file_path,
            tool_name="write",
            allowlist=allowlist,
            denylist=denylist,
            config_permission=config_permission,
            sensitive_patterns=sensitive_patterns,
        )

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case parameter names
            file_path = self._get_param(input_data, "filePath", "file_path")
            content = self._get_param(input_data, "content")

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
                    error=f"File already exists: {file_path}. To edit an existing file, use the edit tool instead. The write tool is only for creating new files."
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

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    def resolve_permission(self, args: dict) -> PermissionContext | None:
        """Resolve permission for directory listing with trust-folder and workdir checks."""
        path = args.get("path")
        if not path:
            return None

        from core.config.settings import Settings

        settings = Settings()
        allowlist = settings.tools.get("allowlist", [])
        denylist = settings.tools.get("denylist", [])

        result = resolve_path_permission(
            path,
            allowlist=allowlist,
            denylist=denylist,
        )
        if result is not None:
            return result

        if not is_path_within_workdir(path):
            from pathlib import Path

            resolved = Path(path).expanduser().resolve()
            parent_dir = str(resolved.parent)
            glob = str(Path(parent_dir) / "*")
            return PermissionContext(
                permission=ToolPermission.ASK,
                required_permissions=[
                    RequiredPermission(
                        scope=PermissionScope.OUTSIDE_DIRECTORY,
                        invocation_pattern=str(resolved),
                        session_pattern=glob,
                        label=f"list {resolved}",
                    )
                ],
            )

        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            path = self._get_param(input_data, "path")

            if not isinstance(path, str) or not path:
                return ToolOutput(success=False, result=None, error="Invalid directory path: path parameter must be a non-empty string. Please provide a valid absolute directory path.")

            if not os.path.exists(path):
                return ToolOutput(success=False, result=None, error=f"Directory not found: {path}. Please verify the directory path is correct and exists. Use glob to search for directories if you're unsure of the exact path.")

            if not os.path.isdir(path):
                return ToolOutput(success=False, result=None, error=f"Path is not a directory: {path}. The provided path exists but is a file, not a directory. Please provide a directory path or use read to read this file.")

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

    name = "glob"
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
- Use grep instead when searching for content within files

IMPORTANT: Use parameter name 'maxResults' (camelCase) not 'max_results'."""
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

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case
            query = self._get_param(input_data, "query")
            max_results = self._get_param(input_data, "maxResults", "max_results")

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
