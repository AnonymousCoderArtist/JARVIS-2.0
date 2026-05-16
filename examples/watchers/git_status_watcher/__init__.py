"""Git status watcher — monitors repository state."""

from core.watchers.base import BaseWatcher


class GitStatusWatcher(BaseWatcher):
    """Watches git repository status and updates COP with branch, uncommitted changes, and remote sync state."""

    name = "git_status"
    description = "Monitors git repository status (branch, changes, ahead/behind)"

    def __init__(self):
        super().__init__(interval=30)  # Check every 30 seconds
        self._last_status = None

    async def watch(self):
        """Fetch git status and persist to COP."""
        import subprocess

        try:
            # Get current branch
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()

            # Get short status (branch info + ahead/behind)
            status = subprocess.check_output(
                ["git", "status", "--short", "--branch"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()

            # Parse ahead/behind
            ahead = 0
            behind = 0
            for line in status.split("\n"):
                if line.startswith("##"):
                    if "ahead" in line:
                        ahead = int(line.split("ahead ")[1].split()[0])
                    if "behind" in line:
                        behind = int(line.split("behind ")[1].split()[0])

            # Count changed files
            changed_files = [l for l in status.split("\n") if not l.startswith("##")]
            uncommitted = len(changed_files)

            data = {
                "branch": branch,
                "uncommitted_changes": uncommitted,
                "ahead": ahead,
                "behind": behind,
                "clean": uncommitted == 0 and ahead == 0 and behind == 0,
            }

            # Persist to COP for agents
            self.update_cop(data)

            # Notify only when state changes from clean → dirty or vice versa
            is_clean = data["clean"]
            was_clean = self._last_status.get("clean", True) if self._last_status else True

            if was_clean and not is_clean:
                await self.notify(
                    "Git Changes Detected",
                    f"Branch {branch}: {uncommitted} uncommitted file(s), "
                    f"{ahead} ahead, {behind} behind remote",
                    level="warning",
                )
            elif not was_clean and is_clean:
                await self.notify(
                    "Repository Clean",
                    f"Branch {branch} is up to date with no uncommitted changes",
                    level="info",
                )

            self._last_status = data

        except subprocess.CalledProcessError:
            # Not a git repo — silently skip
            pass
        except FileNotFoundError:
            # git not installed
            pass
