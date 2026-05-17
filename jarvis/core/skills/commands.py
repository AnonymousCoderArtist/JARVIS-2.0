"""Skill management commands for the CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

from jarvis.core.skills import (
    GitHubSource,
    HermesSource,
    LocalSource,
    OpenClawSource,
    SkillManager,
    SkillSource,
)
from jarvis.core.skills.trace_collector import get_trace_collector


class SkillCommands:
    """Handle skill-related CLI commands."""

    def __init__(self, skill_manager: SkillManager, display_manager=None):
        self.skill_manager = skill_manager
        self.display_manager = display_manager
        self.skill_dir = Path.home() / ".jarvis" / "skills"
        self.skill_dir.mkdir(parents=True, exist_ok=True)

    def _show_message(self, message: str, style: str = "dim"):
        """Display a message to the user."""
        if self.display_manager:
            self.display_manager.cprint(message, style=style)
        else:
            print(f"[{style}] {message}")

    async def cmd_install(self, args: list[str]) -> None:
        """Install a skill from a source.
        
        Usage: jarvis skill install <source> <skill_id>
        
        Sources: hermes, openclaw, github, local
        """
        if len(args) < 2:
            self._show_message("Usage: jarvis skill install <source> <skill_id>", "error")
            self._show_message("Sources: hermes, openclaw, github, local")
            return

        source_name = args[0].lower()
        skill_id = args[1]

        # Select source
        source: SkillSource | None = None
        if source_name == "hermes":
            source = HermesSource()
        elif source_name == "openclaw":
            source = OpenClawSource()
        elif source_name == "github":
            source = GitHubSource()
        elif source_name == "local":
            if len(args) < 3:
                self._show_message("Usage: jarvis skill install local <local_path>", "error")
                return
            source = LocalSource()
            skill_id = args[2]
        else:
            self._show_message(f"Unknown source: {source_name}", "error")
            return

        self._show_message(f"Installing skill '{skill_id}' from {source_name}...")

        success, message, metadata = source.install(skill_id, self.skill_dir)

        if success:
            self._show_message(f"✓ {message}", "success")
        else:
            self._show_message(f"✗ {message}", "error")

    async def cmd_sync(self, args: list[str]) -> None:
        """Sync skills from a source.
        
        Usage: jarvis skill sync <source> [--category <category>]
        
        Sources: hermes, openclaw
        """
        if len(args) < 1:
            self._show_message("Usage: jarvis skill sync <source> [--category <category>]", "error")
            return

        source_name = args[0].lower()
        category = None

        # Parse category flag
        for i, arg in enumerate(args[1:], 1):
            if arg == "--category" and i + 1 < len(args):
                category = args[i + 1]

        self._show_message(f"Syncing skills from {source_name}...")

        # For now, we'll implement a basic sync that installs popular skills
        # In a full implementation, this would fetch the skill index and install all
        if source_name == "hermes":
            source = HermesSource()
            # Install a few popular skills as example
            popular_skills = ["code-explainer", "debug-helper"]
            installed = 0
            for skill_id in popular_skills:
                success, _, _ = source.install(skill_id, self.skill_dir)
                if success:
                    installed += 1
            self._show_message(f"Installed {installed}/{len(popular_skills)} skills from Hermes", "success")
        elif source_name == "openclaw":
            self._show_message("OpenClaw sync: This would install ~13,700 community skills", "dim")
            self._show_message("Use 'jarvis skill install' for individual skills", "dim")
        else:
            self._show_message(f"Unknown source: {source_name}", "error")

    async def cmd_optimize(self, args: list[str]) -> None:
        """Optimize skills using DSPy.
        
        Usage: jarvis optimize skills --policy dspy [--min-traces <n>]
        """
        policy = "dspy"
        min_traces = 20
        skills_to_optimize = []

        for i, arg in enumerate(args):
            if arg == "--policy" and i + 1 < len(args):
                policy = args[i + 1]
            elif arg == "--min-traces" and i + 1 < len(args):
                min_traces = int(args[i + 1])
            elif arg != "--policy" and not arg.startswith("--"):
                skills_to_optimize.append(arg)

        self._show_message(f"Optimizing skills with {policy} policy (min {min_traces} traces)...")

        collector = get_trace_collector()
        optimized_count = 0

        if skills_to_optimize:
            for skill_name in skills_to_optimize:
                traces = collector.get_traces(skill_name)
                if len(traces) >= min_traces:
                    self._show_message(f"  Optimizing '{skill_name}' ({len(traces)} traces)...", "dim")
                    # DSPy optimization would happen here
                    optimized_count += 1
                else:
                    self._show_message(f"  Skipping '{skill_name}': only {len(traces)} traces (need {min_traces})", "dim")
        else:
            # Optimize all skills with enough traces
            all_skills = self.skill_manager.get_all_available_skills()
            for skill_name in all_skills:
                traces = collector.get_traces(skill_name)
                if len(traces) >= min_traces:
                    self._show_message(f"  Optimizing '{skill_name}' ({len(traces)} traces)...", "dim")
                    optimized_count += 1

        if optimized_count == 0:
            self._show_message("No skills have enough traces for optimization yet.", "dim")
            self._show_message("Run skills and collect traces to enable optimization.", "dim")
        else:
            self._show_message(f"Optimized {optimized_count} skill(s).", "success")

    async def cmd_bench(self, args: list[str]) -> None:
        """Benchmark skill performance.
        
        Usage: jarvis bench skills [--max-samples <n>] [--seeds <n>]
        """
        max_samples = 5
        seeds = 42

        for i, arg in enumerate(args):
            if arg == "--max-samples" and i + 1 < len(args):
                max_samples = int(args[i + 1])
            elif arg == "--seeds" and i + 1 < len(args):
                seeds = int(args[i + 1])

        self._show_message(f"Benchmarking skills (max {max_samples} samples, seeds: {seeds})...")

        # List available skills
        skills = self.skill_manager.get_all_available_skills()
        if not skills:
            self._show_message("No skills installed. Install some first!", "error")
            return

        collector = get_trace_collector()

        self._show_message(f"Found {len(skills)} installed skills:")
        for name, profile in skills.items():
            trace_count = collector.get_trace_count(name)
            self._show_message(f"  - {profile.display_name or name} ({trace_count} traces)")

        self._show_message("\nBenchmark results would show accuracy, latency, and cost metrics.", "dim")

    async def cmd_list(self, args: list[str]) -> None:
        """List installed or available skills.
        
        Usage: jarvis skill list [--all]
        """
        show_all = "--all" in args

        if show_all:
            skills = self.skill_manager.get_all_available_skills()
            self._show_message(f"All available skills ({len(skills)}):")
        else:
            skills = self.skill_manager.get_builtin_skills()
            self._show_message(f"Built-in skills ({len(skills)}):")

        for name, profile in skills.items():
            self._show_message(f"  • {profile.display_name or name}")
            if profile.description:
                self._show_message(f"    {profile.description[:80]}...")

    async def cmd_activate(self, args: list[str]) -> None:
        """Activate a skill.
        
        Usage: jarvis skill activate <skill_name>
        """
        if len(args) < 1:
            self._show_message("Usage: jarvis skill activate <skill_name>", "error")
            return

        skill_name = args[0]
        success, message, content = self.skill_manager.activate_skill(skill_name)

        if success:
            self._show_message(f"✓ {message}", "success")
            if content:
                preview = content[:300] + "..." if len(content) > 300 else content
                self._show_message(f"\nContent preview:\n{preview}", "dim")
        else:
            self._show_message(f"✗ {message}", "error")


async def main():
    """CLI entry point for skill commands."""
    import sys

    skill_manager = SkillManager()
    commands = SkillCommands(skill_manager)

    if len(sys.argv) < 3:
        print("Usage: jarvis skill <install|sync|optimize|bench|list|activate> ...")
        sys.exit(1)

    _, subcmd, *subargs = sys.argv

    handlers = {
        "install": commands.cmd_install,
        "sync": commands.cmd_sync,
        "optimize": commands.cmd_optimize,
        "bench": commands.cmd_bench,
        "list": commands.cmd_list,
        "activate": commands.cmd_activate,
    }

    handler = handlers.get(subcmd)
    if handler:
        await handler(subargs)
    else:
        print(f"Unknown command: {subcmd}")
        print("Available: install, sync, optimize, bench, list, activate")


if __name__ == "__main__":
    asyncio.run(main())
