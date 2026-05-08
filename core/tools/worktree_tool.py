"""Worktree management tools for JARVIS."""

from __future__ import annotations

import os

from .base import BaseTool, ToolInput, ToolOutput
from .worktree_utils import (
    countWorktreeChanges,
    createWorktreeForSession,
    getCurrentWorktreeSession,
    keepWorktree,
    killTmuxSession,
    saveWorktreeState,
    validateWorktreeSlug,
)


class EnterWorktreeTool(BaseTool):
    """Tool for creating and entering a git worktree."""

    name = "enter_worktree"
    description = """Creates an isolated git worktree and switches the session into it.

WHEN TO USE:
- The user explicitly mentions "worktree" (e.g., "start a worktree", "create a worktree")

REQUIREMENTS:
- Must be in a git repository
- Must not already be in a worktree created by this session

BEHAVIOR:
- Creates a new git worktree inside .jarvis/worktrees/<slug>/
- Creates a new branch based on HEAD
- Optionally creates a tmux session for the worktree
- Switches the session's working directory to the new worktree
"""

    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Optional name for the worktree. If not provided, a random name is generated. Each '/'-separated segment may contain only letters, digits, dots, underscores, and dashes; max 64 chars total.",
            }
        },
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        name = getattr(input_data, "name", None) or self._generate_random_name()

        # Validate not already in a worktree created by this session
        existing_session = getCurrentWorktreeSession()
        if existing_session:
            return ToolOutput(
                success=False,
                error="Already in a worktree session. Use exit_worktree first.",
                result=None,
            )

        # Validate slug
        try:
            validateWorktreeSlug(name)
        except ValueError as e:
            return ToolOutput(
                success=False,
                error=str(e),
                result=None,
            )

        try:
            # Generate session ID
            import uuid
            sessionId = str(uuid.uuid4())[:8]

            # Create the worktree
            session = await createWorktreeForSession(sessionId, name)

            # Change to the worktree directory
            os.chdir(session.worktreePath)

            # Save session state
            saveWorktreeState(session)

            # Get branch info for message
            branchInfo = f" on branch {session.worktreeBranch}" if session.worktreeBranch else ""

            return ToolOutput(
                success=True,
                result=session.worktreePath,
                metadata={
                    "worktreePath": session.worktreePath,
                    "worktreeBranch": session.worktreeBranch,
                    "message": f"Created worktree at {session.worktreePath}{branchInfo}. The session is now working in the worktree. Use exit_worktree to leave mid-session.",
                },
            )
        except RuntimeError as e:
            return ToolOutput(
                success=False,
                error=str(e),
                result=None,
            )
        except Exception as e:
            return ToolOutput(
                success=False,
                error=f"Failed to create worktree: {str(e)}",
                result=None,
            )

    def _generate_random_name(self) -> str:
        """Generate a random worktree name."""
        import secrets
        import string
        suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        return f"worktree-{suffix}"


class ExitWorktreeTool(BaseTool):
    """Tool for exiting a git worktree and returning to the original directory."""

    name = "exit_worktree"
    description = """Exit a worktree session created by enter_worktree and return to the original working directory.

SCOPE:
- This tool ONLY operates on worktrees created by enter_worktree in this session
- It will NOT touch worktrees created manually or in a previous session

WHEN TO USE:
- The user explicitly asks to "exit the worktree", "leave the worktree", "go back"

PARAMETERS:
- action: "keep" or "remove"
  - "keep": Leave the worktree and branch on disk
  - "remove": Delete the worktree directory and its branch
- discard_changes: (optional, default false) Required when removing with uncommitted changes
"""

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["keep", "remove"],
                "description": '"keep" leaves the worktree and branch on disk; "remove" deletes both.',
            },
            "discard_changes": {
                "type": "boolean",
                "description": "Required true when action is 'remove' and the worktree has uncommitted files or unmerged commits.",
            },
        },
        "required": ["action"],
    }

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        action = getattr(input_data, "action", "keep")
        discardChanges = getattr(input_data, "discard_changes", False)

        # Check for active worktree session
        session = getCurrentWorktreeSession()
        if not session:
            return ToolOutput(
                success=True,
                result=None,
                metadata={
                    "message": "No-op: There is no active worktree session to exit. This tool only operates on worktrees created by enter_worktree in the current session. No filesystem changes were made.",
                },
            )

        # Validate action is valid
        if action not in ("keep", "remove"):
            return ToolOutput(
                success=False,
                error=f"Invalid action: {action}. Must be 'keep' or 'remove'.",
                result=None,
            )

        # For remove action, check for changes if discard_changes is not set
        if action == "remove" and not discardChanges:
            summary = await countWorktreeChanges(
                session.worktreePath, session.originalHeadCommit
            )
            if summary is None:
                return ToolOutput(
                    success=False,
                    error=f"Could not verify worktree state at {session.worktreePath}. Refusing to remove without explicit confirmation. Re-invoke with discard_changes: true to proceed — or use action: 'keep' to preserve the worktree.",
                    result=None,
                )

            if summary["changedFiles"] > 0 or summary["commits"] > 0:
                parts = []
                if summary["changedFiles"] > 0:
                    parts.append(f"{summary['changedFiles']} uncommitted {'file' if summary['changedFiles'] == 1 else 'files'}")
                if summary["commits"] > 0:
                    parts.append(f"{summary['commits']} {'commit' if summary['commits'] == 1 else 'commits'} on {session.worktreeBranch or 'the worktree branch'}")

                return ToolOutput(
                    success=False,
                    error=f"Worktree has {', '.join(parts)}. Removing will discard this work permanently. Confirm with the user, then re-invoke with discard_changes: true — or use action: 'keep' to preserve the worktree.",
                    result=None,
                )

        # Capture values before operation
        originalCwd = session.originalCwd
        worktreePath = session.worktreePath
        worktreeBranch = session.worktreeBranch
        tmuxSessionName = session.tmuxSessionName

        # Re-count changes for accurate messaging
        summary = await countWorktreeChanges(worktreePath, session.originalHeadCommit)
        changedFiles = summary["changedFiles"] if summary else 0
        commits = summary["commits"] if summary else 0

        # Execute the action
        if action == "keep":
            await keepWorktree()
            saveWorktreeState(None)

            tmuxNote = f" Tmux session {tmuxSessionName} is still running; reattach with: tmux attach -t {tmuxSessionName}" if tmuxSessionName else ""
            message = f"Exited worktree. Your work is preserved at {worktreePath}{f' on branch {worktreeBranch}' if worktreeBranch else ''}. Session is now back in {originalCwd}.{tmuxNote}"

            return ToolOutput(
                success=True,
                result=worktreePath,
                metadata={
                    "action": "keep",
                    "originalCwd": originalCwd,
                    "worktreePath": worktreePath,
                    "worktreeBranch": worktreeBranch,
                    "tmuxSessionName": tmuxSessionName,
                    "message": message,
                },
            )

        # action == "remove"
        # Kill tmux session if exists before cleanup
        if tmuxSessionName:
            # Use cleanupWorktree which handles both tmux and git cleanup
            import asyncio

            async def _removeWorktree():
                await killTmuxSession(tmuxSessionName)
                process = await asyncio.create_subprocess_exec(
                    "git", "worktree", "remove", worktreePath, "--force",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                if worktreeBranch:
                    process2 = await asyncio.create_subprocess_exec(
                        "git", "branch", "-D", worktreeBranch,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await process2.communicate()

            await _removeWorktree()
        else:
            # No tmux, just do the git cleanup
            import asyncio
            process = await asyncio.create_subprocess_exec(
                "git", "worktree", "remove", worktreePath, "--force",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            if worktreeBranch:
                process2 = await asyncio.create_subprocess_exec(
                    "git", "branch", "-D", worktreeBranch,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process2.communicate()

        # Return to original directory
        os.chdir(originalCwd)

        # Return to original directory
        os.chdir(originalCwd)

        # Remove session state
        saveWorktreeState(None)

        discardParts = []
        if commits > 0:
            discardParts.append(f"{commits} {'commit' if commits == 1 else 'commits'}")
        if changedFiles > 0:
            discardParts.append(f"{changedFiles} uncommitted {'file' if changedFiles == 1 else 'files'}")

        discardNote = f" Discarded {', '.join(discardParts)}." if discardParts else ""
        message = f"Exited and removed worktree at {worktreePath}.{discardNote} Session is now back in {originalCwd}."

        return ToolOutput(
            success=True,
            result=worktreePath,
            metadata={
                "action": "remove",
                "originalCwd": originalCwd,
                "worktreePath": worktreePath,
                "worktreeBranch": worktreeBranch,
                "discardedFiles": changedFiles,
                "discardedCommits": commits,
                "message": message,
            },
        )
