"""File editing tool for text replacement"""

import difflib
import os

from .base import BaseTool, ToolInput, ToolOutput


class ReplaceTool(BaseTool):
    """Tool for replacing text in a file"""

    name = "replace"
    description = "Replace text within files. Requires exact match including whitespace and indentation. Use the replacements array for single or multiple edits."
    input_schema = {
        "type": "object",
        "properties": {
            "replacements": {
                "type": "array",
                "description": "Array of replacement operations. Each operation should have file_path, old_string, and new_string. For a single replacement, provide an array with one item.",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute or relative path to the file to modify",
                            "minLength": 1
                        },
                        "old_string": {
                            "type": "string",
                            "description": "The exact literal text to replace (must match exactly including whitespace and indentation)"
                        },
                        "new_string": {
                            "type": "string",
                            "description": "The exact literal text to replace with"
                        }
                    },
                    "required": ["file_path", "old_string", "new_string"]
                },
                "minItems": 1
            }
        },
        "required": ["replacements"]
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        try:
            replacements = getattr(input_data, "replacements", None)

            if not isinstance(replacements, list) or not replacements:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="No replacements provided. Use the 'replacements' array with at least one item."
                )

            return await self._execute_multiple_replacements(replacements)

        except Exception as e:
            return ToolOutput(
                success=False, result=None, error=f"Failed to replace text: {str(e)}"
            )

    async def _execute_multiple_replacements(self, replacements: list[dict[str, str]]) -> ToolOutput:
        """Execute multiple replacement operations in a single call"""
        results = []
        errors = []

        for i, replacement in enumerate(replacements):
            try:
                file_path = replacement.get("file_path")
                old_string = replacement.get("old_string")
                new_string = replacement.get("new_string")

                if not isinstance(file_path, str) or not file_path:
                    errors.append(f"Replacement {i + 1}: Missing required parameters")
                    continue

                if not isinstance(old_string, str) or not old_string:
                    errors.append(f"Replacement {i + 1}: Missing required parameters")
                    continue

                if not isinstance(new_string, str):
                    errors.append(f"Replacement {i + 1}: Missing required parameters")
                    continue

                if not os.path.exists(file_path):
                    errors.append(f"Replacement {i + 1}: File not found: {file_path}")
                    continue

                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                count = content.count(old_string)
                if count == 0:
                    errors.append(f"Replacement {i + 1}: Could not find 'old_string' in {file_path}")
                    continue

                if count > 1:
                    errors.append(f"Replacement {i + 1}: Found {count} occurrences in {file_path}. Use allow_multiple for bulk replacements.")
                    continue

                new_content = content.replace(old_string, new_string, 1)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                diff_output = self._generate_diff(content, new_content, file_path)
                results.append({
                    "file": file_path,
                    "file_path": file_path,
                    "status": "success",
                    "occurrences_replaced": 1,
                    "diff": diff_output,
                    "unified_diff": diff_output,
                })

            except Exception as e:
                errors.append(f"Replacement {i + 1}: {str(e)}")

        success = len(errors) == 0
        result_message = f"Completed {len(results)} replacements successfully"
        if errors:
            result_message += f"\nErrors: {len(errors)} replacements failed\n" + "\n".join(errors)

        return ToolOutput(
            success=success,
            result=result_message,
            metadata={
                "total_replacements": len(replacements),
                "successful": len(results),
                "failed": len(errors),
                "results": results
            }
        )

    def _generate_diff(self, original: str, new: str, filename: str) -> str:
        """Generate unified diff between two strings"""
        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )

        return "".join(diff)
