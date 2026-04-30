"""Key bindings module for JARVIS CLI - handles custom key bindings and shortcuts."""

from typing import Dict, Callable, Any, Optional
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings, ConditionalKeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.keys import Keys

from .config import ConfigManager
from .display import DisplayManager


class KeyBindingManager:
    """Manages custom key bindings for the CLI."""
    
    def __init__(self, config_manager: ConfigManager, display_manager: DisplayManager):
        self.config_manager = config_manager
        self.display_manager = display_manager
        self.key_bindings = KeyBindings()
        self.custom_handlers: Dict[str, Callable] = {}
        self._setup_default_bindings()
        self._setup_custom_bindings()
    
    def _setup_default_bindings(self):
        """Setup default key bindings."""
        
        @self.key_bindings.add(Keys.ControlC)
        def _(event):
            """Handle Ctrl+C - interrupt current operation."""
            event.app.exit(exception=KeyboardInterrupt("User interrupted"))
        
        @self.key_bindings.add(Keys.ControlD)
        def _(event):
            """Handle Ctrl+D - exit."""
            event.app.exit()
        
        @self.key_bindings.add(Keys.ControlL)
        def _(event):
            """Handle Ctrl+L - clear screen."""
            self.display_manager.clear_screen()
            event.app.renderer.clear()
        
        @self.key_bindings.add(Keys.ControlT)
        def _(event):
            """Handle Ctrl+T - show status."""
            # This will be handled by the command handler
            event.app.current_buffer.insert_text("/status")
            event.app.current_buffer.validate_and_handle()
        
        @self.key_bindings.add(Keys.ControlH)
        def _(event):
            """Handle Ctrl+H - show help."""
            event.app.current_buffer.insert_text("/help")
            event.app.current_buffer.validate_and_handle()
        
        @self.key_bindings.add(Keys.F1)
        def _(event):
            """Handle F1 - show help."""
            event.app.current_buffer.insert_text("/help")
            event.app.current_buffer.validate_and_handle()
        
        @self.key_bindings.add(Keys.F5)
        def _(event):
            """Handle F5 - clear screen."""
            self.display_manager.clear_screen()
            event.app.renderer.clear()
        
        @self.key_bindings.add(Keys.F10)
        def _(event):
            """Handle F10 - exit."""
            event.app.exit()
    
    def _setup_custom_bindings(self):
        """Setup custom key bindings from configuration."""
        custom_bindings = self.config_manager.config.keybindings.custom_bindings
        
        # Map of key names to prompt_toolkit Keys
        key_map = {
            "ctrl_c": Keys.ControlC,
            "ctrl_d": Keys.ControlD,
            "ctrl_l": Keys.ControlL,
            "ctrl_t": Keys.ControlT,
            "ctrl_h": Keys.ControlH,
            "ctrl_w": Keys.ControlW,
            "ctrl_u": Keys.ControlU,
            "ctrl_k": Keys.ControlK,
            "ctrl_a": Keys.ControlA,
            "ctrl_e": Keys.ControlE,
            "ctrl_p": Keys.ControlP,
            "ctrl_n": Keys.ControlN,
            "ctrl_b": Keys.ControlB,
            "ctrl_f": Keys.ControlF,
            "ctrl_r": Keys.ControlR,
            "ctrl_s": Keys.ControlS,
            "ctrl_g": Keys.ControlG,
            "ctrl_x": Keys.ControlX,
            "ctrl_y": Keys.ControlY,
            "ctrl_z": Keys.ControlZ,
            "ctrl_o": Keys.ControlO,
            "ctrl_v": Keys.ControlV,
            "ctrl_q": Keys.ControlQ,
            "tab": Keys.Tab,
            "enter": Keys.Enter,
            "escape": Keys.Escape,
            "space": " ",
            "backspace": Keys.Backspace,
            "delete": Keys.Delete,
            "up": Keys.Up,
            "down": Keys.Down,
            "left": Keys.Left,
            "right": Keys.Right,
            "home": Keys.Home,
            "end": Keys.End,
            "page_up": Keys.PageUp,
            "page_down": Keys.PageDown,
            "f1": Keys.F1,
            "f2": Keys.F2,
            "f3": Keys.F3,
            "f4": Keys.F4,
            "f5": Keys.F5,
            "f6": Keys.F6,
            "f7": Keys.F7,
            "f8": Keys.F8,
            "f9": Keys.F9,
            "f10": Keys.F10,
            "f11": Keys.F11,
            "f12": Keys.F12,
        }
        
        for action, key_name in custom_bindings.items():
            if key_name.lower() in key_map:
                key = key_map[key_name.lower()]
                self._add_custom_key_binding(key, action)
    
    def _add_custom_key_binding(self, key, action: str):
        """Add a custom key binding."""
        
        @self.key_bindings.add(key)
        def _(event):
            """Handle custom key binding."""
            if action in self.custom_handlers:
                self.custom_handlers[action](event)
            else:
                # Handle built-in actions
                self._handle_builtin_action(action, event)
    
    def _handle_builtin_action(self, action: str, event):
        """Handle built-in key actions."""
        if action == "clear":
            self.display_manager.clear_screen()
            event.app.renderer.clear()
        elif action == "help":
            event.app.current_buffer.insert_text("/help")
            event.app.current_buffer.validate_and_handle()
        elif action == "status":
            event.app.current_buffer.insert_text("/status")
            event.app.current_buffer.validate_and_handle()
        elif action == "exit":
            event.app.exit()
        elif action == "interrupt":
            event.app.exit(exception=KeyboardInterrupt("User interrupted"))
        elif action == "save_config":
            self.config_manager.save_config()
            self.display_manager.show_success("Configuration saved")
        elif action == "reload_config":
            self.config_manager._load_config()
            self.display_manager.show_success("Configuration reloaded")
    
    def register_handler(self, action: str, handler: Callable):
        """Register a custom handler for an action."""
        self.custom_handlers[action] = handler
    
    def add_key_binding(self, key_name: str, action: str):
        """Add a new key binding."""
        self.config_manager.set_key_binding(action, key_name)
        self._setup_custom_bindings()  # Rebuild bindings
    
    def get_key_bindings(self) -> KeyBindings:
        """Get the key bindings for prompt_toolkit."""
        return self.key_bindings
    
    def list_bindings(self) -> Dict[str, str]:
        """List all current key bindings."""
        return self.config_manager.config.keybindings.custom_bindings


class ViKeyBindings:
    """Vi-style key bindings for the CLI."""
    
    @staticmethod
    def create_vi_bindings() -> KeyBindings:
        """Create Vi-style key bindings."""
        bindings = KeyBindings()
        
        # Normal mode bindings
        @bindings.add(Keys.Escape)
        def _(event):
            """Enter normal mode."""
            event.app.vi_state.input_mode = "navigation"
        
        # Navigation
        @bindings.add("h", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Move left."""
            event.app.current_buffer.cursor_left()
        
        @bindings.add("l", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Move right."""
            event.app.current_buffer.cursor_right()
        
        @bindings.add("j", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Move down."""
            event.app.current_buffer.cursor_down()
        
        @bindings.add("k", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Move up."""
            event.app.current_buffer.cursor_up()
        
        # Insert mode
        @bindings.add("i", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Enter insert mode."""
            event.app.vi_state.input_mode = "insert"
        
        @bindings.add("a", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Append after cursor."""
            event.app.vi_state.input_mode = "insert"
            event.app.current_buffer.cursor_right()
        
        # Commands
        @bindings.add(":", filter=Condition(lambda app: app.vi_state.input_mode == "navigation"))
        def _(event):
            """Enter command mode."""
            event.app.current_buffer.insert_text(":")
            event.app.vi_state.input_mode = "insert"
        
        return bindings


class EmacsKeyBindings:
    """Emacs-style key bindings for the CLI."""
    
    @staticmethod
    def create_emacs_bindings() -> KeyBindings:
        """Create Emacs-style key bindings."""
        bindings = KeyBindings()
        
        # Movement
        @bindings.add(Keys.ControlA)
        def _(event):
            """Beginning of line."""
            event.app.current_buffer.start_of_line()
        
        @bindings.add(Keys.ControlE)
        def _(event):
            """End of line."""
            event.app.current_buffer.end_of_line()
        
        @bindings.add(Keys.ControlP)
        def _(event):
            """Previous line."""
            event.app.current_buffer.cursor_up()
        
        @bindings.add(Keys.ControlN)
        def _(event):
            """Next line."""
            event.app.current_buffer.cursor_down()
        
        @bindings.add(Keys.ControlB)
        def _(event):
            """Backward character."""
            event.app.current_buffer.cursor_left()
        
        @bindings.add(Keys.ControlF)
        def _(event):
            """Forward character."""
            event.app.current_buffer.cursor_right()
        
        # Editing
        @bindings.add(Keys.ControlK)
        def _(event):
            """Kill to end of line."""
            buffer = event.app.current_buffer
            buffer.delete(buffer.cursor_position, len(buffer.text))
        
        @bindings.add(Keys.ControlU)
        def _(event):
            """Kill to beginning of line."""
            buffer = event.app.current_buffer
            buffer.delete(0, buffer.cursor_position)
        
        @bindings.add(Keys.ControlW)
        def _(event):
            """Kill word."""
            buffer = event.app.current_buffer
            word_start = buffer.document.find_start_of_previous_word()
            if word_start is not None:
                buffer.delete(word_start, buffer.cursor_position)
        
        # History
        @bindings.add(Keys.ControlR)
        def _(event):
            """Search backward."""
            event.app.current_buffer.start_history_reverse_search()
        
        @bindings.add(Keys.ControlS)
        def _(event):
            """Search forward."""
            event.app.current_buffer.start_history_forward_search()
        
        return bindings


def create_key_bindings(config_manager: ConfigManager, display_manager: DisplayManager) -> KeyBindings:
    """Create appropriate key bindings based on configuration."""
    manager = KeyBindingManager(config_manager, display_manager)
    
    mode = config_manager.config.keybindings.mode.lower()
    
    if mode == "vi":
        vi_bindings = ViKeyBindings.create_vi_bindings()
        return ConditionalKeyBindings(vi_bindings, Condition(lambda app: True))
    elif mode == "emacs":
        emacs_bindings = EmacsKeyBindings.create_emacs_bindings()
        return ConditionalKeyBindings(emacs_bindings, Condition(lambda app: True))
    else:
        # Default/custom bindings
        return manager.get_key_bindings()
