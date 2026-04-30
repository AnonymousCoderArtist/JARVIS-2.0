"""Commands module for JARVIS CLI - handles command parsing, routing, and execution."""

import asyncio
import shlex
import sys
from typing import Callable, Awaitable, Dict, List, Optional, Any

from .display import DisplayManager


class Command:
    """Base class for CLI commands."""
    
    def __init__(self, name: str, description: str, handler: Callable[[List[str]], Awaitable[None]]):
        self.name = name
        self.description = description
        self.handler = handler
    
    async def execute(self, args: List[str]) -> None:
        """Execute the command with given arguments."""
        await self.handler(args)


class CommandRegistry:
    """Registry for managing CLI commands."""
    
    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
        self.commands: Dict[str, Command] = {}
        self.aliases: Dict[str, str] = {}
        self._register_builtin_commands()
    
    def _register_builtin_commands(self):
        """Register built-in CLI commands."""
        self.register(Command("help", "Show available commands", self._cmd_help))
        self.register(Command("clear", "Clear the screen", self._cmd_clear))
        self.register(Command("status", "Show system status", self._cmd_status))
        self.register(Command("exit", "Exit JARVIS", self._cmd_exit))
        self.register(Command("quit", "Exit JARVIS", self._cmd_exit))
        
        # Add aliases
        self.add_alias("h", "help")
        self.add_alias("cls", "clear")
        self.add_alias("st", "status")
    
    def register(self, command: Command):
        """Register a new command."""
        self.commands[command.name] = command
    
    def add_alias(self, alias: str, command_name: str):
        """Add an alias for an existing command."""
        if command_name in self.commands:
            self.aliases[alias] = command_name
    
    def get_command(self, name: str) -> Optional[Command]:
        """Get command by name or alias."""
        # Check direct command name
        if name in self.commands:
            return self.commands[name]
        
        # Check aliases
        if name in self.aliases:
            return self.commands[self.aliases[name]]
        
        return None
    
    def list_commands(self) -> List[Command]:
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
    
    async def _cmd_help(self, args: List[str]):
        """Handle help command."""
        self.display_manager.show_help()
    
    async def _cmd_clear(self, args: List[str]):
        """Handle clear command."""
        self.display_manager.clear_screen()
        # Re-show banner and help after clear
        # This will be handled by the main CLI
    
    async def _cmd_status(self, args: List[str]):
        """Handle status command."""
        # This will be updated with actual status from CLI
        self.display_manager.show_status(
            model="Loading...", 
            sdk="Loading...", 
            base_url="Loading...", 
            tool_count=0
        )
    
    async def _cmd_exit(self, args: List[str]):
        """Handle exit command."""
        self.display_manager.cprint("Goodbye!", color="green")
        sys.exit(0)




class ShellCommand:
    """Handles shell command execution."""
    
    def __init__(self, display_manager: DisplayManager):
        self.display_manager = display_manager
    
    async def execute(self, command: str) -> bool:
        """Execute a shell command."""
        if not command.strip():
            return False
        
        self.display_manager.console.print()
        self.display_manager.console.print("shell", style="dim")
        self.display_manager.console.print(f"$ {command}", style="dim")
        self.display_manager.console.print()
        
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
                self.display_manager.console.print()
                error_panel = self.display_manager.console.print(
                    stderr.decode(),
                    style="red bold"
                )
            
            self.display_manager.console.print()
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
        async def _cmd_status(args: List[str]):
            self.display_manager.show_status(model, sdk, base_url, tool_count)
        
        # Replace the status command handler
        self.command_registry.register(
            Command("status", "Show system status", _cmd_status)
        )
    
