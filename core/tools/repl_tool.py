"""REPL tool for interactive Python execution (OpenClaude style) - OpenJarvis compatible version

Full security implementation with:
- Pattern blocklist to prevent dangerous operations
- Restricted builtins to remove dangerous functions
- Safe import allowlist to whitelist only safe modules
- Session management with LRU eviction
- Thread-safe execution
- Output truncation
- Support for both eval (expressions) and exec (statements)
"""

import asyncio
import builtins
import io
import threading
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import BaseTool, ToolInput, ToolOutput


# ============================================================================
# SECURITY LAYERS
# ============================================================================

# Layer 1: Pattern blocklist - blocks dangerous code patterns
_BLOCKED_PATTERNS = [
    "os.system",
    "os.popen",
    "subprocess",
    "shutil.rmtree",
    "shutil.move",
    "shutil.copy",
    "__import__",
    "open(",
    "ctypes",
    "socket",
    "http.client",
    "urllib",
    "requests.",
    "eval(",
    "exec(",
    "compile(",
    "globals()",
    "locals()",
    "vars()",
    "memoryview",
    "mmap",
    "ptrace",
    "sys.settrace",
    "sys.setprofile",
    "exit(",
    "quit(",
    "os._exit",
    "os.kill",
    "os.chmod",
    "os.chown",
]

# Layer 2: Restricted builtins - remove dangerous built-in functions
_REMOVED_BUILTINS = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "breakpoint",
    "exit",
    "quit",
    "input",
    "globals",
    "locals",
    "vars",
    "dir",
    "help",
    "copyright",
    "credits",
    "license",
    "exit",
    "quit",
}

# Layer 3: Safe import allowlist - only these modules can be imported
_SAFE_IMPORT_MODULES = frozenset({
    "math",
    "cmath",
    "decimal",
    "fractions",
    "random",
    "statistics",
    "itertools",
    "functools",
    "operator",
    "collections",
    "string",
    "re",
    "textwrap",
    "datetime",
    "time",
    "calendar",
    "json",
    "csv",
    "copy",
    "dataclasses",
    "enum",
    "typing",
    "heapq",
    "bisect",
    "array",
    "pprint",
    "abc",
    "numbers",
    "pathlib",
    "hashlib",
    "secrets",
    "base64",
    "binascii",
    "html",
    "xml",
    "urllib.parse",
    "uuid",
})


def _make_safe_import(allowed: frozenset = _SAFE_IMPORT_MODULES):
    """Create a custom __import__ that only allows safe modules."""
    # Get the real import function
    if isinstance(__builtins__, dict):
        real_import = __builtins__["__import__"]
    else:
        real_import = __builtins__.__import__

    def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
        top_level = name.split(".")[0]
        if top_level not in allowed:
            raise ImportError(
                f"Import of '{name}' is not allowed. "
                f"Allowed modules: {', '.join(sorted(allowed))}"
            )
        return real_import(name, *args, **kwargs)

    return _safe_import


def _make_restricted_builtins() -> Dict[str, Any]:
    """Build a builtins dict with dangerous functions removed."""
    safe = {k: v for k, v in vars(builtins).items() if k not in _REMOVED_BUILTINS}
    safe["__import__"] = _make_safe_import()
    return safe


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@dataclass
class ReplSession:
    """Represents a REPL session with persistent state."""
    session_id: str
    namespace: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    execution_count: int = 0


class REPLTool(BaseTool):
    """Tool for interactive Python REPL execution (OpenClaude style) - Fully secured
    
    Security Features:
    - Pattern blocklist prevents dangerous operations
    - Restricted builtins remove dangerous functions
    - Safe import allowlist only allows whitelisted modules
    
    Features:
    - Session management with LRU eviction
    - Thread-safe execution
    - Output truncation
    - Support for both eval (expressions) and exec (statements)
    - Execution timeout
    """

    name = "repl"
    description = """Execute Python code in a secure REPL with state persistence.

WHEN TO USE:
- Testing small code snippets
- Quick calculations or data transformations
- Checking Python syntax
- Working with math or string operations

DO NOT USE for: File operations, network requests, or installing packages!

Parameters:
- code (REQUIRED): Python code to execute
- session_id (OPTIONAL): Session ID for state persistence (auto-created if not provided)
- timeout (OPTIONAL): Execution timeout in seconds (default: 30)
- reset (OPTIONAL): Reset session state before execution (default: false)
- max_output (OPTIONAL): Maximum characters in output (default: 10000)

Security: Dangerous operations blocked, imports restricted to safe modules only.
State persists across calls within the same session_id."""

    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "session_id": {"type": "string", "description": "Session ID for state persistence (optional, auto-created if not provided)"},
            "timeout": {"type": "integer", "description": "Execution timeout in seconds (default: 30)"},
            "reset": {"type": "boolean", "description": "Reset the session state before execution (default: false)"},
            "max_output": {"type": "integer", "description": "Maximum characters in output (default: 10000)"}
        },
        "required": ["code"]
    }

    # Configuration
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_OUTPUT = 10000
    DEFAULT_MAX_SESSIONS = 16

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_output: int = DEFAULT_MAX_OUTPUT,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
    ):
        """Initialize the REPL tool with configurable limits."""
        self._timeout = timeout
        self._max_output = max_output
        self._max_sessions = max_sessions
        self._sessions: Dict[str, ReplSession] = {}
        self._lock = threading.Lock()

    def _get_param(self, input_data: ToolInput, *names) -> Any:
        """Get parameter using multiple possible names (camelCase and snake_case)."""
        for name in names:
            value = getattr(input_data, name, None)
            if value is not None:
                return value
        return None

    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute Python code in a secure REPL context."""
        try:
            # Support both camelCase and snake_case parameter names
            code = self._get_param(input_data, "code")
            session_id = self._get_param(input_data, "session_id", "sessionId")
            timeout = self._get_param(input_data, "timeout") or self._timeout
            reset = self._get_param(input_data, "reset") or False
            max_output = self._get_param(input_data, "max_output") or self._max_output

            # Validate code parameter
            if not isinstance(code, str) or not code:
                return ToolOutput(
                    success=False,
                    result=None,
                    error="Invalid code: code parameter must be a non-empty string. Please provide valid Python code to execute."
                )

            # Validate session_id
            if session_id is None:
                session_id = "default"
            if not isinstance(session_id, str) or not session_id:
                session_id = "default"

            # Validate timeout
            if not isinstance(timeout, int) or timeout <= 0:
                timeout = self._timeout

            # Validate max_output
            if not isinstance(max_output, int) or max_output <= 0:
                max_output = self._max_output

            # SECURITY CHECK - Pattern blocklist
            blocked_pattern = self._check_blocked_patterns(code)
            if blocked_pattern:
                return ToolOutput(
                    success=False,
                    result=None,
                    error=f"Security blocked: code contains prohibited pattern '{blocked_pattern}'. This pattern is not allowed for security reasons."
                )

            # Resolve session (get or create)
            session = self._resolve_session(session_id, reset)

            # Execute code with timeout
            output, success = await self._exec_with_timeout(
                code, session, timeout
            )

            # Update session metadata
            session.last_used = time.time()
            session.execution_count += 1

            # Truncate output if too large
            if len(output) > max_output:
                output = output[:max_output] + "\n... (output truncated)"

            if not output:
                output = "(no output)"

            return ToolOutput(
                success=success,
                result=output,
                metadata={
                    "session_id": session.session_id,
                    "execution_count": session.execution_count,
                    "created_at": session.created_at,
                    "last_used": session.last_used,
                }
            )

        except Exception as e:
            return ToolOutput(
                success=False,
                result=None,
                error=f"Failed to execute REPL code: {str(e)}. Please check if your Python code is syntactically correct and if required modules are installed."
            )

    def _check_blocked_patterns(self, code: str) -> Optional[str]:
        """Check if code contains any blocked patterns."""
        for pattern in _BLOCKED_PATTERNS:
            if pattern in code:
                return pattern
        return None

    def _resolve_session(
        self,
        session_id: str,
        reset: bool = False,
    ) -> ReplSession:
        """Get or create a session, with LRU eviction at max_sessions."""
        with self._lock:
            if session_id in self._sessions and not reset:
                return self._sessions[session_id]

            if session_id in self._sessions and reset:
                # Reset existing session
                session = self._sessions[session_id]
                session.namespace = {"__builtins__": _make_restricted_builtins()}
                session.execution_count = 0
                return session

            # Create new session
            sid = session_id or str(uuid.uuid4())

            # LRU eviction if at capacity
            if len(self._sessions) >= self._max_sessions:
                oldest_id = min(
                    self._sessions,
                    key=lambda k: self._sessions[k].last_used,
                )
                del self._sessions[oldest_id]

            session = ReplSession(
                session_id=sid,
                namespace={"__builtins__": _make_restricted_builtins()},
            )
            self._sessions[sid] = session
            return session

    async def _exec_with_timeout(
        self,
        code: str,
        session: ReplSession,
        timeout: int,
    ) -> tuple[str, bool]:
        """Execute code with timeout support.

        Returns (output, success).
        """
        result_holder: Dict[str, Any] = {"output": "", "success": True}

        def _run() -> None:
            """Run code in a separate thread."""
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            try:
                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                    # Try eval first for expression display (REPL-like behavior)
                    try:
                        compiled = compile(code, "<repl>", "eval")
                        val = eval(compiled, session.namespace)
                        if val is not None:
                            print(repr(val))
                    except SyntaxError:
                        # Not an expression — execute as statements
                        compiled = compile(code, "<repl>", "exec")
                        exec(compiled, session.namespace)
            except Exception as exc:
                result_holder["output"] = f"{type(exc).__name__}: {exc}"
                result_holder["success"] = False
                return

            output = stdout_buf.getvalue()
            err = stderr_buf.getvalue()
            if err:
                output += ("\n" if output else "") + err
            result_holder["output"] = output

        # Run in a thread with timeout
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._run_with_timeout, _run, timeout, result_holder)

        return result_holder["output"], result_holder["success"]

    def _run_with_timeout(self, target, timeout: int, result_holder: Dict[str, Any]) -> None:
        """Run target function with timeout."""
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            result_holder["output"] = f"Execution timed out after {timeout} seconds."
            result_holder["success"] = False

    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================

    def clear_session(self, session_id: str = "default") -> bool:
        """Clear a REPL session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def list_sessions(self) -> list[Dict[str, Any]]:
        """List all active REPL sessions with metadata."""
        with self._lock:
            return [
                {
                    "session_id": sid,
                    "execution_count": sess.execution_count,
                    "created_at": sess.created_at,
                    "last_used": sess.last_used,
                }
                for sid, sess in self._sessions.items()
            ]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific session."""
        with self._lock:
            if session_id in self._sessions:
                sess = self._sessions[session_id]
                return {
                    "session_id": sess.session_id,
                    "execution_count": sess.execution_count,
                    "created_at": sess.created_at,
                    "last_used": sess.last_used,
                    "variables": list(sess.namespace.keys()),
                }
            return None

    def reset_all_sessions(self) -> int:
        """Reset all sessions. Returns number of sessions cleared."""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count


# ============================================================================
# LEGACY API - For backward compatibility
# ============================================================================

# Class-level session storage (legacy compatibility)
_REPLTool = REPLTool


class REPLToolLegacy:
    """Legacy REPLTool class for backward compatibility.
    
    This is now a wrapper around the secured REPLTool.
    """
    
    _sessions: dict[str, dict] = {}
    
    @staticmethod
    def create_secured() -> REPLTool:
        """Create a new secured REPL tool instance."""
        return REPLTool()


# Export the main class
__all__ = ["REPLTool", "REPLToolLegacy"]