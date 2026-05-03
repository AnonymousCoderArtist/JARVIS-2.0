"""Grep tool for searching file contents"""

import asyncio
import fnmatch
import os
import re
import subprocess
from typing import Any

from .base import BaseTool, ToolInput, ToolOutput


class GrepSearchTool(BaseTool):
    """Tool for searching file contents (OpenClaude style)"""

    name = "grep"
    description = """Search file contents by text or regex pattern.

Parameters:
- query (required): Search pattern (text or regex with alternation like 'word1|word2')
- isRegexp (optional): Set true if query is a regex pattern (default: false)
- includePattern (optional): Filter files by glob (e.g., '*.py', 'src/**')
- maxResults (optional): Maximum number of results to return

Case-insensitive search. Uses ripgrep (rg) for speed, falls back to Python regex.
Returns matching lines with file path, line number, and content."""
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The pattern to search for in files in the workspace. Use regex with alternation (e.g., 'word1|word2|word3') or character classes to find multiple potential words in a single search. Be sure to set the isRegexp property properly to declare whether it's a regex or plain text pattern. Is case-insensitive.",
                "minLength": 1
            },
            "isRegexp": {
                "type": "boolean",
                "description": "Whether the pattern is a regex (default: false)"
            },
            "includePattern": {
                "type": "string",
                "description": "Search files matching this glob pattern. Will be applied to the relative path of files within the workspace. To search recursively inside a folder, use a proper glob pattern like \"src/folder/**\". Do not use | in includePattern."
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

    def _check_ripgrep_available(self) -> bool:
        """Check if ripgrep (rg) is available on the system"""
        try:
            result = subprocess.run(["rg", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def _search_with_ripgrep(self, query: str, is_regexp: bool, include_pattern: str, max_results: int) -> tuple:
        """Search using ripgrep (rg) for faster results"""
        try:
            # Build ripgrep command
            cmd = ["rg"]

            # Case insensitive search (Copilot Chat default)
            cmd.append("-i")

            # Add pattern
            if is_regexp:
                cmd.append(query)
            else:
                cmd.append(re.escape(query))

            # Include pattern
            if include_pattern:
                cmd.extend(["-g", include_pattern])

            # Output format: file path, line number, and content
            cmd.extend(["--no-heading", "--no-column", "--line-number", "--color=never"])

            # Limit results
            if max_results:
                cmd.extend(["-m", str(max_results)])

            # Search from current directory
            cmd.append(".")

            # Run ripgrep
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode != 0 and process.returncode != 1:  # 1 means no matches found
                error = stderr.decode() if stderr else "Unknown error"
                return [], 0, error

            # Parse output - remove duplicates
            results = []
            seen = set()
            output = stdout.decode('utf-8', errors='ignore')


            for line in output.splitlines():
                if not line.strip():
                    continue
                # Format: filepath:line_number:content
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    filepath = parts[0]
                    line_num = parts[1]
                    content = parts[2]
                    try:
                        key = (filepath, int(line_num), content.strip())
                        if key not in seen:
                            seen.add(key)
                            results.append({
                                "file": filepath,
                                "line": int(line_num),
                                "content": content.strip()
                            })
                    except ValueError:
                        continue

            return results, len(results), None

        except asyncio.TimeoutError:
            return [], 0, "Ripgrep search timed out"
        except Exception as e:
            return [], 0, str(e)

    async def _search_with_python(self, query: str, is_regexp: bool, include_pattern: str, max_results: int) -> tuple:
        """Search using Python regex as fallback"""
        try:
            # Prepare regex (case-insensitive by default like Copilot Chat)
            flags = re.IGNORECASE
            if is_regexp:
                try:
                    search_re = re.compile(query, flags)
                except re.error as e:
                    return [], 0, f"Invalid regex: {str(e)}"
            else:
                search_re = re.compile(re.escape(query), flags)

            results = []
            total_matches = 0

            # Search from current working directory (workspace root)
            search_path = os.getcwd()

            for root, _dirs, files in os.walk(search_path):
                for filename in files:
                    filepath = os.path.join(root, filename)

                    # Filter by include_pattern
                    if include_pattern:
                        rel_path = os.path.relpath(filepath, search_path)
                        if not fnmatch.fnmatch(rel_path, include_pattern):
                            continue

                    try:
                        with open(filepath, encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines):
                                if search_re.search(line):
                                    total_matches += 1
                                    results.append({
                                        "file": filepath,
                                        "line": i + 1,
                                        "content": line.strip()
                                    })
                                    if max_results and len(results) >= max_results:
                                        break
                    except (OSError, IOError):
                        continue

                    if max_results and len(results) >= max_results:
                        break

            return results, total_matches, None

        except Exception as e:
            return [], 0, str(e)

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            # Support both camelCase and snake_case parameter names
            query = self._get_param(input_data, "query")
            is_regexp = self._get_param(input_data, "isRegexp", "is_regexp")
            include_pattern = self._get_param(input_data, "includePattern", "include_pattern")
            max_results = self._get_param(input_data, "maxResults", "max_results")

            if not isinstance(query, str) or not query:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid search query: query parameter must be a non-empty string. Please provide a valid search pattern or text to find."
                )

            if not isinstance(is_regexp, bool):
                is_regexp = False

            if not isinstance(include_pattern, str):
                include_pattern = ""

            if not isinstance(max_results, int):
                max_results = 0

            # Try ripgrep first for faster results
            if self._check_ripgrep_available():
                results, total_matches, error = await self._search_with_ripgrep(query, is_regexp, include_pattern, max_results)
                if error:
                    return ToolOutput(success=False, result=None, error=f"Ripgrep search failed: {error}")
            else:
                # Fall back to Python regex
                results, total_matches, error = await self._search_with_python(query, is_regexp, include_pattern, max_results)
                if error:
                    return ToolOutput(success=False, result=None, error=f"Python search failed: {error}")

            return ToolOutput(
                success=True,
                result=results,
                metadata={"query": query, "total_matches": total_matches}
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Grep search failed: {str(e)}. Please check if your search pattern is valid and if you have permission to access the search directories."
            )