"""Grep tool for searching file contents"""

import asyncio
import fnmatch
import os
import re
import subprocess

from .base import BaseTool, ToolInput, ToolOutput


class GrepSearchTool(BaseTool):
    """Tool for searching file contents (OpenClaude style)"""

    name = "grep"
    description = """Do a fast text search in the workspace. Use this tool when you want to search with an exact string or regex pattern.

Usage:
- Use regex patterns with alternation (|) or character classes to search for multiple potential words at once instead of making separate searches
- For example, use 'function|method|procedure' to look for all of those words at once
- Use includePattern to search within files matching a specific pattern, or in a specific file, using a relative path
- Use this tool when you want to see an overview of a particular file, instead of using read many times to look for code within a file
- Search is case-insensitive by default
- Use maxResults to limit the number of results if needed
- Set isRegexp to true when using regex patterns, false for exact string matches
- This tool uses ripgrep (rg) if available for faster results, otherwise falls back to Python regex"""
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
                "description": "Whether the pattern is a regex"
            },
            "includePattern": {
                "type": "string",
                "description": "Search files matching this glob pattern. Will be applied to the relative path of files within the workspace. To search recursively inside a folder, use a proper glob pattern like \"src/folder/**\". Do not use | in includePattern."
            },
            "maxResults": {
                "type": "number",
                "description": "The maximum number of results to return. Do not use this unless necessary, it can slow things down. By default, only some matches are returned. If you use this and don't see what you're looking for, you can try again with a more specific query or a larger maxResults.",
                "minimum": 1
            }
        },
        "required": ["query", "isRegexp"]
    }

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

            # Parse output
            results = []
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

                                    if max_results and total_matches >= max_results:
                                        break
                    except Exception:
                        pass

                    if max_results and total_matches >= max_results:
                        break

                if max_results and total_matches >= max_results:
                    break

            return results, total_matches, None

        except Exception as e:
            return [], 0, str(e)

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            query = getattr(input_data, "query", None)
            is_regexp = getattr(input_data, "isRegexp", False)
            include_pattern = getattr(input_data, "includePattern", None)
            max_results = getattr(input_data, "maxResults", None)

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
