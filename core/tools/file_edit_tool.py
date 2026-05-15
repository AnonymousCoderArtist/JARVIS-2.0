"""File editing tool for text replacement"""

import difflib
import os
from typing import Any

from core.tools.permissions import (
    PermissionContext,
    ToolPermission,
    resolve_file_tool_permission,
)

from .base import BaseTool, ToolInput, ToolOutput


class EditTool(BaseTool):
    """Tool for editing files"""

    name = "edit"
    description = """Edit existing files by replacing exact text strings.

WHEN TO USE:
- Modifying existing code
- Fixing bugs or updating logic
- Refactoring code
- ALWAYS read file first with 'read' tool before editing!

Parameters:
- replacements (REQUIRED): Array of replacement operations, each with:
  - filePath: Absolute or relative path to file
  - oldString: Exact text to replace (MUST match exactly including whitespace)
  - newString: Replacement text

CRITICAL: old_string must match exactly - use 'read' first to get current content.
Copy text including all whitespace/indentation. Include context lines for uniqueness.
Supports multiple replacements in single call."""
    input_schema = {
        "type": "object",
        "properties": {
            "replacements": {
                "type": "array",
                "description": "Array of replacement operations. Each operation should have file_path, old_string, and new_string. For a single replacement, provide an array with one item.",
                "items": {
                    "type": "object",
                    "properties": {
                        "filePath": {
                            "type": "string",
                            "description": "Absolute or relative path to the file",
                            "minLength": 1
                        },
                        "oldString": {
                            "type": "string",
                            "description": "The exact literal text to replace (must match exactly including whitespace and indentation)"
                        },
                        "newString": {
                            "type": "string",
                            "description": "The exact literal text to replace with"
                        }
                    },
                    "required": ["oldString", "newString"]
                },
                "minItems": 1
            }
        },
        "required": ["replacements"]
    }

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names"""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    def resolve_permission(self, args: dict) -> PermissionContext | None:
        """Resolve permission for file edit operation with granular checks"""
        import json

        replacements = args.get("replacements", [])
        if not replacements:
            return None

        # Handle case where replacements is a JSON string
        if isinstance(replacements, str):
            try:
                replacements = json.loads(replacements)
            except json.JSONDecodeError:
                return None

        if not isinstance(replacements, list) or not replacements:
            return None

        # Get the first replacement and handle if it's a JSON string
        first_replacement = replacements[0]
        if isinstance(first_replacement, str):
            try:
                first_replacement = json.loads(first_replacement)
            except json.JSONDecodeError:
                return None

        if not isinstance(first_replacement, dict):
            return None

        # Check the first file path for permission
        first_file = first_replacement.get("filePath")
        if not first_file:
            return None

        # Get configuration
        from core.config.settings import Settings
        settings = Settings()
        allowlist = settings.tools.get("allowlist", [])
        denylist = settings.tools.get("denylist", [])
        sensitive_patterns = settings.tools.get("sensitive_patterns", [])
        config_permission = ToolPermission(
            settings.tools.get("edit", {}).get("permission", "ask")
        )

        return resolve_file_tool_permission(
            first_file,
            tool_name="edit",
            allowlist=allowlist,
            denylist=denylist,
            config_permission=config_permission,
            sensitive_patterns=sensitive_patterns,
        )

    async def edit(self, input_data: ToolInput) -> ToolOutput:
        """Edit files by replacing text"""
        try:
            replacements = self._get_param(input_data, "replacements")

            if not isinstance(replacements, list) or not replacements:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="No replacements provided. Use the 'replacements' array with at least one item. Each replacement should be an object with 'file_path', 'old_string', and 'new_string' properties. Example: {\"replacements\": [{\"file_path\": \"path/to/file.py\", \"old_string\": \"old text\", \"new_string\": \"new text\"}]}"
                )

            return await self._execute_multiple_replacements(replacements)

        except Exception as e:
            return ToolOutput(
                success=False, result=None, error=f"Failed to edit text: {str(e)}"
            )

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute the edit (calls edit method)"""
        return await self.edit(input_data)

    async def _execute_multiple_replacements(self, replacements: list[dict[str, str]]) -> ToolOutput:
        """Execute multiple replacement operations in a single call"""
        import json

        results = []
        errors = []

        for i, replacement in enumerate(replacements):
            try:
                # Handle case where replacement is a JSON string
                if isinstance(replacement, str):
                    try:
                        replacement = json.loads(replacement)
                    except json.JSONDecodeError:
                        errors.append(f"Replacement {i + 1}: Invalid JSON string provided. Please provide a valid replacement object.")
                        continue

                if not isinstance(replacement, dict):
                    errors.append(f"Replacement {i + 1}: Invalid replacement format. Expected an object with 'file_path', 'old_string', and 'new_string' properties.")
                    continue

                # Support camelCase parameters
                file_path = replacement.get("filePath")
                old_string = replacement.get("oldString")
                new_string = replacement.get("newString")

                if not isinstance(file_path, str) or not file_path:
                    errors.append(f"Replacement {i + 1}: Missing or invalid file_path. Please provide a valid absolute file path.")
                    continue

                if not isinstance(old_string, str) or not old_string:
                    errors.append(f"Replacement {i + 1}: Missing or invalid old_string. Please provide the exact text to replace as a string.")
                    continue

                if not isinstance(new_string, str):
                    errors.append(f"Replacement {i + 1}: Missing or invalid new_string. Please provide the replacement text as a string.")
                    continue

                # Check if old_string and new_string are identical
                if old_string == new_string:
                    errors.append(f"Replacement {i + 1}: The old_string and new_string are identical. No change will be made.")
                    continue

                if not os.path.exists(file_path):
                    errors.append(f"Replacement {i + 1}: File not found: {file_path}. Please verify the file path is correct and the file exists. Use list_directory or glob to find the correct file path.")
                    continue

                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                count = content.count(old_string)
                if count == 0:
                    errors.append(f"Replacement {i + 1}: Could not find 'old_string' in {file_path}. The text you're trying to replace doesn't exist exactly as written. Please re-read the file using the read tool to see the current content, then copy the exact text including all whitespace, indentation, and special characters. Pay close attention to tabs vs spaces and any hidden characters.")
                    continue

                if count > 1:
                    errors.append(f"Replacement {i + 1}: Found {count} occurrences of the string in {file_path}. Please re-read the file to see all occurrences, then provide more surrounding context (more lines before/after) to make the replacement unique, or use multiple replacement operations to handle each occurrence separately.")
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
                errors.append(f"Replacement {i + 1}: {str(e)}. Please check if you have permission to modify the file and if the file path is correct.")

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
