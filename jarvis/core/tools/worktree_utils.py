"""Git worktree management utilities for JARVIS."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Worktree state - module level to persist across tool calls
_current_worktree_session: WorktreeSession | None = None

# Constants
WORKTREE_DIR = ".jarvis/worktrees"
MAX_WORKTREE_SLUG_LENGTH = 64
VALID_WORKTREE_SLUG_SEGMENT = __import__("re").compile(r"^[a-zA-Z0-9._-]+$")


@dataclass
class WorktreeSession:
    """Session state for an active worktree."""

    originalCwd: str
    worktreePath: str
    worktreeName: str
    sessionId: str = ""
    worktreeBranch: str | None = None
    originalHeadCommit: str | None = None
    tmuxSessionName: str | None = None


def validateWorktreeSlug(slug: str) -> None:
    """
    Validate a worktree slug to prevent path traversal and directory escape.

    The slug is joined into `.jarvis/worktrees/<slug>` via Path, which
    normalizes `..` segments — so `../../../target` would escape the worktrees
    directory.

    Forward slashes are allowed for nesting (e.g. `feature/foo`).
    """
    if not slug:
        raise ValueError("Worktree name cannot be empty")
    if len(slug) > MAX_WORKTREE_SLUG_LENGTH:
        raise ValueError(
            f"Invalid worktree name: must be {MAX_WORKTREE_SLUG_LENGTH} characters or fewer (got {len(slug)})"
        )

    for segment in slug.split("/"):
        if segment in (".", ".."):
            raise ValueError(
                'Invalid worktree name: must not contain "." or ".." path segments'
            )
        if not VALID_WORKTREE_SLUG_SEGMENT.match(segment):
            raise ValueError(
                'Invalid worktree name: each "/"-separated segment must be non-empty and contain only letters, digits, dots, underscores, and dashes'
            )


def getCurrentWorktreeSession() -> WorktreeSession | None:
    """Get the current worktree session, if any."""
    return _current_worktree_session


def saveWorktreeState(session: WorktreeSession | None) -> None:
    """Save or clear the current worktree session state."""
    global _current_worktree_session
    _current_worktree_session = session


async def _runGitCommand(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            process.returncode or 0,
            stdout.decode() if stdout else "",
            stderr.decode() if stderr else "",
        )
    except FileNotFoundError:
        return 1, "", "git command not found"


async def findGitRoot(path: str) -> str | None:
    """Find the git root directory for the given path."""
    code, stdout, _ = await _runGitCommand(["rev-parse", "--show-toplevel"], cwd=path)
    if code == 0:
        return stdout.strip()
    return None


async def getGitBranch(path: str) -> str | None:
    """Get the current git branch name."""
    code, stdout, _ = await _runGitCommand(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=path
    )
    if code == 0:
        return stdout.strip()
    return None


async def getHeadCommit(path: str) -> str | None:
    """Get the current HEAD commit hash."""
    code, stdout, _ = await _runGitCommand(["rev-parse", "HEAD"], cwd=path)
    if code == 0:
        return stdout.strip()
    return None


async def getDefaultBranch(path: str) -> str:
    """Get the default branch name (main or master)."""
    code, stdout, _ = await _runGitCommand(
        ["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=path
    )
    if code == 0:
        # Format: refs/remotes/origin/main
        return stdout.strip().split("/")[-1]
    return "main"


async def isTmuxAvailable() -> bool:
    """Check if tmux is available on the system."""
    try:
        process = await asyncio.create_subprocess_exec(
            "tmux", "-V", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return process.returncode == 0
    except FileNotFoundError:
        return False


async def createTmuxSession(sessionName: str) -> bool:
    """Create a tmux session with the given name."""
    try:
        process = await asyncio.create_subprocess_exec(
            "tmux", "new-session", "-d", "-s", sessionName
        )
        await process.communicate()
        return process.returncode == 0
    except FileNotFoundError:
        return False


async def killTmuxSession(sessionName: str) -> bool:
    """Kill a tmux session by name."""
    try:
        process = await asyncio.create_subprocess_exec(
            "tmux", "kill-session", "-t", sessionName,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return process.returncode == 0
    except FileNotFoundError:
        return False


def generateTmuxSessionName(sessionId: str) -> str:
    """Generate a tmux session name for a worktree."""
    return f"jarvis-{sessionId[:8]}"


async def countWorktreeChanges(
    worktreePath: str, originalHeadCommit: str | None
) -> dict[str, Any] | None:
    """
    Count uncommitted changes in a worktree.

    Returns None if state cannot be reliably determined (fail-closed).
    Returns dict with changedFiles and commits on success.
    """
    # Check for uncommitted files
    code, stdout, _ = await _runGitCommand(
        ["status", "--porcelain"], cwd=worktreePath
    )
    if code != 0:
        return None

    changedFiles = sum(1 for line in stdout.strip().split("\n") if line.strip())

    if not originalHeadCommit:
        # No baseline - can't count commits, fail closed
        return None

    # Count new commits
    code, stdout, _ = await _runGitCommand(
        ["rev-list", "--count", f"{originalHeadCommit}..HEAD"], cwd=worktreePath
    )
    if code != 0:
        return None

    commits = int(stdout.strip()) if stdout.strip() else 0

    return {"changedFiles": changedFiles, "commits": commits}


async def createWorktreeForSession(sessionId: str, slug: str) -> WorktreeSession:
    """
    Create a new git worktree for the given session.

    Returns a WorktreeSession with all relevant details.
    """
    currentPath = os.getcwd()
    originalCwd = os.path.abspath(currentPath)

    # Validate slug
    validateWorktreeSlug(slug)

    # Find git root
    gitRoot = await findGitRoot(currentPath)
    if not gitRoot:
        raise RuntimeError("Not in a git repository")

    # Resolve to main repo root (in case we're already in a worktree)
    if gitRoot != currentPath:
        os.chdir(gitRoot)

    # Get current commit
    originalHeadCommit = await getHeadCommit(gitRoot)

    # Create worktree path
    worktreeDir = Path(WORKTREE_DIR)
    worktreeDir.mkdir(parents=True, exist_ok=True)
    worktreePath = str((Path(gitRoot) / worktreeDir / slug).resolve())

    # Create branch name
    worktreeBranch = f"jarvis-{slug}"

    # Create the worktree
    code, _, stderr = await _runGitCommand(
        ["worktree", "add", worktreePath, "-b", worktreeBranch]
    )
    if code != 0:
        raise RuntimeError(f"Failed to create worktree: {stderr}")

    # Check for tmux
    tmuxSessionName = None
    if await isTmuxAvailable():
        tmuxSessionName = generateTmuxSessionName(sessionId)
        if await createTmuxSession(tmuxSessionName):
            pass  # Success
        else:
            tmuxSessionName = None  # Fall back to no tmux

    session = WorktreeSession(
        originalCwd=originalCwd,
        worktreePath=worktreePath,
        worktreeName=slug,
        sessionId=sessionId,
        worktreeBranch=worktreeBranch,
        originalHeadCommit=originalHeadCommit,
        tmuxSessionName=tmuxSessionName,
    )

    return session


async def keepWorktree() -> None:
    """
    Keep the worktree but return to original directory.

    This removes the worktree entry from .git/worktrees but keeps
    the actual directory and branch intact.
    """
    global _current_worktree_session
    session = _current_worktree_session

    if not session:
        return

    # Remove worktree reference but keep files
    await _runGitCommand(["worktree", "remove", session.worktreePath, "--force"])

    # Return to original directory
    os.chdir(session.originalCwd)


async def cleanupWorktree() -> None:
    """
    Remove the worktree entirely.

    This deletes both the worktree directory and its branch.
    """
    global _current_worktree_session
    session = _current_worktree_session

    if not session:
        return

    # Kill tmux session if exists
    if session.tmuxSessionName:
        await killTmuxSession(session.tmuxSessionName)

    # Remove worktree and branch
    code, stdout, stderr = await _runGitCommand(
        ["worktree", "remove", session.worktreePath, "--force"]
    )
    if code == 0:
        # Also delete the branch (it's prunable since worktree was removed)
        await _runGitCommand(["branch", "-D", session.worktreeBranch or ""])

    # Return to original directory
    os.chdir(session.originalCwd)
