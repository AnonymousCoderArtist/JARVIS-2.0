"""Commands module for JARVIS CLI - handles command parsing, routing, and execution."""

import asyncio
import shlex
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from core.clipboard import copy_to_clipboard
from core.history import ConversationHistory
from core.trusted_folders import trusted_folders_manager

from .display import DisplayManager


class Command:
    """Base class for CLI commands."""

    def __init__(self, name: str, description: str, handler: Callable[[list[str]], Awaitable[None]], hidden: bool = False):
        self.name = name
        self.description = description
        self.handler = handler
        self.hidden = hidden

    async def execute(self, args: list[str]) -> None:
        """Execute the command with given arguments."""
        await self.handler(args)


class CommandRegistry:
    """Registry for managing CLI commands."""

    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
        self.commands: dict[str, Command] = {}
        self.aliases: dict[str, str] = {}
        self._register_builtin_commands()

    def _register_builtin_commands(self):
        """Register built-in CLI commands."""
        self.register(Command("help", "Show available commands", self._cmd_help))
        self.register(Command("clear", "Clear the screen", self._cmd_clear))
        self.register(Command("status", "Show system status", self._cmd_status))
        self.register(Command("rewind", "Rewind conversation to a previous message", self._cmd_rewind))
        self.register(Command("trust", "Trust a folder for this session and future runs", self._cmd_trust))
        self.register(Command("untrust", "Mark a folder as untrusted", self._cmd_untrust))
        self.register(Command("trust-status", "Show current trust-folder status", self._cmd_trust_status))
        self.register(Command("history", "Show conversation history", self._cmd_history))
        self.register(Command("clear-history", "Clear current session history", self._cmd_clear_history))
        self.register(Command("sessions", "List available sessions", self._cmd_sessions))
        self.register(Command("new-session", "Start a new session with fresh history", self._cmd_new_session))
        self.register(Command("copy", "Copy the last assistant answer to clipboard", self._cmd_copy))
        self.register(Command("themes", "List and change UI themes", self._cmd_themes))
        self.register(Command("exit", "Exit JARVIS", self._cmd_exit))
        self.register(Command("quit", "Exit JARVIS", self._cmd_exit))

        # Add aliases
        self.add_alias("h", "help")
        self.add_alias("cls", "clear")
        self.add_alias("st", "status")
        self.add_alias("rw", "rewind")
        self.add_alias("th", "themes")

    def register(self, command: Command):
        """Register a new command."""
        self.commands[command.name] = command

    def add_alias(self, alias: str, command_name: str):
        """Add an alias for an existing command."""
        if command_name in self.commands:
            self.aliases[alias] = command_name

    def get_command(self, name: str) -> Command | None:
        """Get command by name or alias."""
        # Check direct command name
        if name in self.commands:
            return self.commands[name]

        # Check aliases
        if name in self.aliases:
            return self.commands[self.aliases[name]]

        return None

    def list_commands(self) -> list[Command]:
        """List all registered commands."""
        return list(self.commands.values())

    async def execute_command(self, command_line: str) -> bool:
        """Execute a command from a command line string."""
        if not command_line.startswith("/"):
            return False

        try:
            parts = shlex.split(command_line)
            if not parts:
                return False

            cmd_name = parts[0].lstrip("/").lower()
            args = parts[1:] if len(parts) > 1 else []

            command = self.get_command(cmd_name)
            if command:
                await command.execute(args)
                return True
            else:
                self.display_manager.show_error(f"Unknown command: {cmd_name}")
                return False

        except Exception as e:
            self.display_manager.show_error(f"Command execution error: {e}")
            return False

    # Built-in command handlers

    async def _cmd_help(self, args: list[str]):
        """Handle help command."""
        self.display_manager.show_help()

    async def _cmd_clear(self, args: list[str]):
        """Handle clear command."""
        self.display_manager.clear_screen()
        # Re-show banner and help after clear
        # This will be handled by the main CLI

    async def _cmd_status(self, args: list[str]):
        """Handle status command."""
        # This will be updated with actual status from CLI
        self.display_manager.show_status(
            model="Loading...",
            sdk="Loading...",
            base_url="Loading...",
            tool_count=0
        )

    async def _cmd_rewind(self, args: list[str]):
        """Handle rewind command."""
        self.display_manager.show_error("Rewind is only available in TUI mode. Launch JARVIS with --tui flag.")

    def _resolve_trust_path(self, args: list[str]) -> Path:
        """Resolve a trust command target path.

        If no path is supplied, default to the current working directory.
        """
        if not args:
            return Path.cwd()

        raw_target = args[0]
        if raw_target in {".", "cwd", "current", "here"}:
            return Path.cwd()

        return Path(raw_target).expanduser().resolve()

    async def _cmd_trust(self, args: list[str]):
        """Trust a folder for the current session and persist the decision."""
        try:
            target = self._resolve_trust_path(args)
            trusted_folders_manager.add_trusted(target)
            trusted_folders_manager.trust_for_session(target)
            self.display_manager.show_success(
                f"Trusted folder: {target}\n\n"
                f"This folder is now trusted for the current session and future runs."
            )
        except Exception as e:
            self.display_manager.show_error(f"Failed to trust folder: {e}")

    async def _cmd_untrust(self, args: list[str]):
        """Mark a folder as untrusted and remove any session trust for it."""
        try:
            target = self._resolve_trust_path(args)
            trusted_folders_manager.add_untrusted(target)
            trusted_folders_manager.untrust_for_session(target)
            self.display_manager.show_success(
                f"Untrusted folder: {target}\n\n"
                f"This folder is now blocked for future runs and removed from session trust."
            )
        except Exception as e:
            self.display_manager.show_error(f"Failed to untrust folder: {e}")

    async def _cmd_trust_status(self, args: list[str]):
        """Show the trust status for the current working directory."""
        try:
            target = self._resolve_trust_path(args)
            status = trusted_folders_manager.is_trusted(target)
            trust_root = trusted_folders_manager.find_trust_root(target)
            stats = trusted_folders_manager.get_stats()

            if status is True:
                status_text = "trusted"
            elif status is False:
                status_text = "untrusted"
            else:
                status_text = "undecided"

            message = (
                f"Path: {target}\n"
                f"Status: {status_text}\n"
                f"Trust root: {trust_root if trust_root else 'none'}\n\n"
                f"Trusted folders: {stats['trusted']}\n"
                f"Untrusted folders: {stats['untrusted']}\n"
                f"Session-trusted folders: {stats['session_trusted']}"
            )
            self.display_manager.show_success(message, title="Trust Status")
        except Exception as e:
            self.display_manager.show_error(f"Failed to read trust status: {e}")

    async def _cmd_history(self, args: list[str]):
        """Show conversation history."""
        try:
            history = ConversationHistory()
            messages = history.get_messages()

            if not messages:
                self.display_manager.show_error("No conversation history found for this session.")
                return

            # Format messages for display
            lines = [f"Session: {history.session_id[:8]}...\n"]
            lines.append("-" * 50)

            for msg in messages[-20:]:  # Show last 20 messages
                role = msg.role
                content = msg.content
                if isinstance(content, str):
                    preview = content[:100] + "..." if len(content) > 100 else content
                else:
                    preview = str(content)[:100]
                lines.append(f"\n[{role}] {preview}")

            self.display_manager.show_success("\n".join(lines), title="History")
        except Exception as e:
            self.display_manager.show_error(f"Failed to read history: {e}")

    async def _cmd_copy(self, args: list[str]):
        """Copy the last assistant answer to clipboard."""
        try:
            # Get the last assistant message
            from core.history import ConversationHistory
            history = ConversationHistory()
            messages = history.get_messages()

            last_assistant = None
            for msg in reversed(messages):
                if msg.role == "assistant" and msg.content:
                    last_assistant = msg
                    break

            if not last_assistant:
                self.display_manager.show_error("No assistant answer available yet.")
                return

            text = last_assistant.content
            if isinstance(text, str):
                copy_to_clipboard(text)
                self.display_manager.show_success(
                    f"Copied {len(text)} chars to clipboard",
                    title="Copy Complete"
                )
            else:
                self.display_manager.show_error("Last message content is not text.")
        except Exception as e:
            self.display_manager.show_error(f"Failed to copy to clipboard: {e}")

    async def _cmd_clear_history(self, args: list[str]):
        """Clear current session history."""
        try:
            history = ConversationHistory()
            history.clear_history()
            self.display_manager.show_success(
                f"Cleared history for session {history.session_id[:8]}...",
                title="History Cleared"
            )
        except Exception as e:
            self.display_manager.show_error(f"Failed to clear history: {e}")

    async def _cmd_new_session(self, args: list[str]):
        """Start a new session with fresh history."""
        try:
            old_session = getattr(self, '_current_session_id', None)
            
            # Use callback if available (CLIInterface handles the actual reset)
            if hasattr(self, 'session_reset_callback') and self.session_reset_callback:
                old_session = await self.session_reset_callback()
                self._current_session_id = self.session_reset_callback.__self__.history.session_id
                new_session = self._current_session_id
            else:
                # Fallback: create new history locally (won't update CLIInterface)
                history = ConversationHistory()
                new_session = history.session_id
                
                # Clear agent memory if available
                if hasattr(self, 'jarvis_agent') and self.jarvis_agent:
                    self.jarvis_agent.clear_memory()
                    self.jarvis_agent.rebuild_system_prompt()
                
                self._current_session_id = new_session
            
            self.display_manager.show_success(
                f"Started new session: {new_session[:8]}...\n"
                f"Previous session: {old_session[:8] if old_session else 'none'}...",
                title="New Session Started"
            )
        except Exception as e:
            self.display_manager.show_error(f"Failed to start new session: {e}")

    async def _cmd_sessions(self, args: list[str]):
        """List available sessions."""
        try:
            history_dir = ConversationHistory().history_dir
            if not history_dir.exists():
                self.display_manager.show_error("No sessions found.")
                return

            sessions = list(history_dir.glob("*.jsonl"))
            if not sessions:
                self.display_manager.show_error("No sessions found.")
                return

            lines = ["Available Sessions:\n"]
            lines.append("-" * 50)

            for session_file in sessions[:10]:  # Show max 10 sessions
                session_id = session_file.stem
                msg_count = sum(1 for _ in open(session_file))
                lines.append(f"\n{session_id[:8]}... ({msg_count} messages)")

            self.display_manager.show_success("\n".join(lines), title="Sessions")
        except Exception as e:
            self.display_manager.show_error(f"Failed to list sessions: {e}")

    async def _cmd_themes(self, args: list[str]):
        """Handle themes command - list or change theme."""
        from .config import CLIConfig
        config = CLIConfig()

        if not args:
            # List available themes
            self.display_manager.show_themes(config.themes, config.display.theme)
            return

        theme_name = args[0].lower()
        available = list(config.themes.keys())

        if theme_name in available:
            try:
                # Note: We need to pass theme change callback to CLI
                self.display_manager.show_success(f"Theme changed to: {theme_name}", title="Theme")
            except Exception as e:
                self.display_manager.show_error(f"Failed to change theme: {e}")
        else:
            self.display_manager.show_error(f"Unknown theme: {theme_name}\nAvailable: {', '.join(available)}")

    async def _cmd_exit(self, args: list[str]):
        """Handle exit command."""
        self.display_manager.cprint("Goodbye!", style="success")
        sys.exit(0)


class ShellCommand:
    """Handles shell command execution."""

    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager

    async def execute(self, command: str) -> bool:
        """Execute a shell command."""
        if not command.strip():
            return False

        self.display_manager.show_rule(f"Shell: {command}", style="secondary")

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if stdout:
                output = stdout.decode()
                if output.strip():
                    self.display_manager.console.print(output)

            if stderr:
                self.display_manager.console.print(stderr.decode(), style="error")

            return True

        except Exception as e:
            self.display_manager.show_error(f"Shell command error: {e}")
            return False


class CommandHandler:
    """Main command handler that orchestrates command and shell execution."""

    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
        self.command_registry = CommandRegistry(display_manager)
        self.shell_command = ShellCommand(display_manager)
        # These will be set by CLIInterface after initialization
        self.agent_manager = None
        self.tool_registry = None
        self.skill_manager = None
        self.jarvis_agent = None

    async def handle_input(self, user_input: str) -> bool:
        """Handle user input and route to appropriate handler."""
        if not user_input.strip():
            return False

        # Handle CLI commands
        if user_input.startswith("/"):
            return await self.command_registry.execute_command(user_input)

        # Handle shell commands
        if user_input.startswith("!"):
            return await self.shell_command.execute(user_input[1:].strip())

        # Regular chat input - not handled here
        return False

    def update_status_info(self, model: str, sdk: str, base_url: str, tool_count: int):
        """Update status information for the status command."""
        # Create a closure that captures the current status
        async def _cmd_status(args: list[str]):
            self.display_manager.show_status(model, sdk, base_url, tool_count)

        # Replace the status command handler
        self.command_registry.register(
            Command("status", "Show system status", _cmd_status)
        )

    def set_managers(self, agent_manager, tool_registry, skill_manager, jarvis_agent, config_manager=None, learning_manager=None, session_reset_callback=None):
        """Set references to managers for command handlers."""
        self.agent_manager = agent_manager
        self.tool_registry = tool_registry
        self.skill_manager = skill_manager
        self.jarvis_agent = jarvis_agent
        self.config_manager = config_manager
        self.learning_manager = learning_manager
        self.session_reset_callback = session_reset_callback

        # Register new commands that depend on these managers
        self._register_profile_command()
        self._register_tools_command()
        self._register_skills_command()
        self._register_skill_command()
        self._register_theme_command()
        self._register_learning_command()

    def _register_theme_command(self):
        """Register theme management commands."""
        async def _cmd_themes(args: list[str]):
            if not self.config_manager:
                self.display_manager.show_error("Config manager not initialized")
                return

            self.display_manager.show_themes(
                self.config_manager.config.themes,
                self.config_manager.config.display.theme
            )

        async def _cmd_theme(args: list[str]):
            if not self.config_manager:
                self.display_manager.show_error("Config manager not initialized")
                return

            if not args:
                self.display_manager.show_error("Usage: /theme <name>")
                return

            theme_name = args[0]
            try:
                self.config_manager.set_theme(theme_name)
                self.display_manager.set_theme(theme_name)
                self.display_manager.show_success(f"Switched to theme: {theme_name}")
                # Save config to persist choice
                self.config_manager.save_config()
            except Exception as e:
                self.display_manager.show_error(f"Failed to switch theme: {e}")

        self.command_registry.register(Command("themes", "List available UI themes", _cmd_themes))
        self.command_registry.register(Command("theme", "Switch UI theme", _cmd_theme))

    def _register_profile_command(self):
        """Register the /profile command."""
        async def _cmd_profile(args: list[str]):
            if not self.agent_manager:
                self.display_manager.show_error("Agent manager not initialized")
                return

            if not args:
                # List available profiles
                profiles = self.agent_manager.list_profiles()
                current = self.agent_manager.get_current_profile()
                self.display_manager.show_profiles(profiles, current)
            else:
                # Switch profile
                profile_name = args[0]
                try:
                    self.agent_manager.switch_profile(profile_name)
                    self.display_manager.show_success(f"Switched to profile: {profile_name}")
                except Exception as e:
                    self.display_manager.show_error(f"Failed to switch profile: {e}")

        self.command_registry.register(Command("profile", "Switch or list agent profiles", _cmd_profile))

    def _register_tools_command(self):
        """Register the /tools command."""
        async def _cmd_tools(args: list[str]):
            if not self.tool_registry:
                self.display_manager.show_error("Tool registry not initialized")
                return

            tools = self.tool_registry.list_tools()
            self.display_manager.show_tools(tools)

        self.command_registry.register(Command("tools", "List available tools", _cmd_tools))

    def _register_skills_command(self):
        """Register the /skills command."""
        async def _cmd_skills(args: list[str]):
            if not self.skill_manager:
                self.display_manager.show_error("Skill manager not initialized")
                return

            if not args:
                # List available skills
                skills = self.skill_manager.get_builtin_skills()
                self.display_manager.show_skills(skills)
            elif args[0] == "activate" and len(args) > 1:
                # Activate a skill
                skill_name = args[1]
                skill = self.skill_manager.get_skill_profile(skill_name)
                if skill:
                    self.display_manager.show_success(f"Skill '{skill_name}' ready for activation")
                    # Get skill content if available
                    content = self.skill_manager.get_skill_content(skill_name)
                    if content:
                        preview = content[:200] + "..." if len(content) > 200 else content
                        self.display_manager.cprint(f"Content: {preview}", style="dim")
                    else:
                        self.display_manager.cprint("No content file found for this skill", style="dim")
                else:
                    self.display_manager.show_error(f"Skill '{skill_name}' not found")
            else:
                self.display_manager.show_error("Usage: /skills [activate <name>]")

        self.command_registry.register(Command("skills", "List and manage skills", _cmd_skills))

    def _register_skill_command(self):
        """Register the /skill command for advanced skill management."""
        from core.skills import SkillManager
        from core.skills.commands import SkillCommands

        skill_manager = self.skill_manager or SkillManager()
        skill_commands = SkillCommands(skill_manager, self.display_manager)

        async def _cmd_skill(args: list[str]):
            if not args:
                self.display_manager.show_error("Usage: /skill <install|sync|optimize|bench|list|activate> ...")
                return

            subcmd = args[0].lower()
            subargs = args[1:]

            handlers = {
                "install": skill_commands.cmd_install,
                "sync": skill_commands.cmd_sync,
                "optimize": skill_commands.cmd_optimize,
                "bench": skill_commands.cmd_bench,
                "list": skill_commands.cmd_list,
                "activate": skill_commands.cmd_activate,
            }

            handler = handlers.get(subcmd)
            if handler:
                await handler(subargs)
            else:
                self.display_manager.show_error(f"Unknown skill command: {subcmd}")
                self.display_manager.show_error("Available: install, sync, optimize, bench, list, activate")

        self.command_registry.register(Command("skill", "Install and manage skills", _cmd_skill))

    def _register_learning_command(self):
        """Register the /learn command."""
        async def _cmd_learn(args: list[str]):
            if not self.learning_manager:
                self.display_manager.show_error("Learning manager not initialized")
                return

            if not args:
                # Show learned preferences
                import asyncio
                prefs = asyncio.run(self.learning_manager.load_preferences())
                self.display_manager.show_learned_preferences(prefs)
            elif args[0] == "analyze":
                # Analyze recent sessions
                import asyncio
                metrics = await self.learning_manager.trace_analyzer.analyze_sessions(limit=10)
                self.display_manager.show_learning_metrics(metrics)
            elif args[0] == "patterns":
                # Show detected patterns
                patterns = self.learning_manager.pattern_detector.detected_patterns
                self.display_manager.show_patterns(patterns)
            else:
                self.display_manager.show_error("Usage: /learn [analyze|patterns]")

        self.command_registry.register(Command("learn", "View learning system status", _cmd_learn))



