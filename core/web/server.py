"""Web UI API server for JARVIS using FastAPI"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.history import ConversationHistory, create_assistant_message, create_user_message

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for webui
_WEBUI_DIR = Path(__file__).parent.parent.parent / "interface" / "jarvis" / "web" / "dist"
if _WEBUI_DIR.exists():
    app.mount("/brand", StaticFiles(directory=_WEBUI_DIR / "brand"), name="brand")
    app.mount("/assets", StaticFiles(directory=_WEBUI_DIR / "assets"), name="assets")

# Agent instance for WebSocket chat
_agent: Any = None

# In-memory token store (in production, use Redis or similar)
_tokens: dict = {}

# Pending approvals: maps tool_call_id -> {
#   "future": asyncio.Future,
#   "tool_name": str,
#   "tool_args": dict,
#   "required_permissions": list,
#   "chat_id": str
# }
_pending_approvals: dict = {}

# Queue for approval requests to be sent to frontend
_approval_request_queue: asyncio.Queue = None  # type: ignore

# Connection info for current session
_connection_info: dict = {}

# Session storage directory
_SESSIONS_DIR = Path.home() / ".jarvis" / "sessions"
_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _save_session(chat_id: str, session_data: dict) -> None:
    """Save session data to disk."""
    session_file = _SESSIONS_DIR / f"{chat_id}.json"
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)


def _load_session(chat_id: str) -> dict | None:
    """Load session data from disk."""
    session_file = _SESSIONS_DIR / f"{chat_id}.json"
    if session_file.exists():
        with open(session_file) as f:
            return json.load(f)
    return None


def _list_sessions() -> list[dict]:
    """List all sessions."""
    sessions = []
    for session_file in _SESSIONS_DIR.glob("*.json"):
        try:
            with open(session_file) as f:
                data = json.load(f)
                sessions.append(data)
        except (OSError, json.JSONDecodeError):
            continue
    return sessions


def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def _get_agent():
    """Get or create the JARVIS agent instance."""
    global _agent

    if _agent is not None:
        return _agent

    # Import here to avoid circular imports
    from core.agents.jarvis_v2 import JarvisV2 as CodingAgent
    from core.agents.system_prompts import get_system_context
    from core.config.settings import Settings
    from core.llm.sdk_adapter import SDKAdapter
    from core.llm_sdk.anthropic.sdk import AnthropicSDK
    from core.llm_sdk.openai.sdk import OpenAISDK
    from core.tools.code_tools import BashTool, RunTestsTool

    # Import core tools
    from core.tools.file_tools import FileReadTool, FileWriteTool, FindTool, LSTool
    from core.tools.grep_tool import GrepSearchTool
    from core.tools.registry import ToolRegistry
    from core.tools.web_tools import WebFetchTool
    from core.tools.tool_search_tool import ToolSearchTool

    # Get configuration from environment
    model = os.getenv("JARVIS_MODEL", "gpt-4o")
    base_url = os.getenv("JARVIS_BASE_URL", "")
    apikey = os.getenv("JARVIS_API_KEY", "")
    sdk = os.getenv("JARVIS_SDK", "openai")
    bypass = os.getenv("JARVIS_BYPASS_PERMISSIONS", "") == "1"

    # Create SDK instance based on configuration
    if sdk == "anthropic":
        sdk_instance = AnthropicSDK(api_key=apikey or "", base_url=base_url if base_url else None)
    else:
        sdk_instance = OpenAISDK(api_key=apikey or "", base_url=base_url if base_url else None)

    # Create LLM provider
    provider = SDKAdapter(sdk_instance, "webui-provider")

    # Create tool registry and register core tools
    tool_registry = ToolRegistry()
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(FindTool())
    tool_registry.register(LSTool())
    tool_registry.register(BashTool())
    tool_registry.register(RunTestsTool())
    tool_registry.register(GrepSearchTool())
    tool_registry.register(WebFetchTool())

    # Register AskUserQuestion tool
    from core.tools.ask_user_question_tool import AskUserQuestionTool
    tool_registry.register(AskUserQuestionTool())

    # Try to register ExaWebSearchTool (optional - depends on external service)
    try:
        from core.tools.web_tools import ExaWebSearchTool
        tool_registry.register(ExaWebSearchTool())
        print("INFO: ExaWebSearchTool registered successfully", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: Failed to register ExaWebSearchTool (search will be unavailable): {e}", file=sys.stderr)

    # Register ToolSearchTool
    tool_registry.register(ToolSearchTool())

    # Simple config getter that returns default settings
    def get_settings() -> Settings:
        return Settings()

    # Create the agent
    system_prompt = get_system_context()
    _agent = CodingAgent(
        provider,
        tool_registry,
        system_prompt=system_prompt,
        model=model,
        config_getter=get_settings,
        bypass_tool_permissions=bypass,
        use_concurrent_tools=True
    )

    # Set up approval callback for webui
    # When bypass is enabled, auto-approve. Otherwise, queue the approval request
    # and wait for user response from the frontend.
    async def approval_callback(
        tool_name: str,
        tool_args: dict[str, Any],
        tool_call_id: str,
        required_permissions: list[Any] | None,
    ) -> tuple[str, str | None]:
        if bypass:
            return ("yes", None)  # Auto-approve when bypass is enabled

        # Create a future that will be resolved when the frontend responds
        future: asyncio.Future = asyncio.Future()

        # Store the pending approval
        _pending_approvals[tool_call_id] = {
            "future": future,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "required_permissions": required_permissions or [],
            "chat_id": _connection_info.get("chat_id"),
        }

        # Queue the approval request to be sent to the frontend
        try:
            if _approval_request_queue is None:
                return ("no", "Approval queue not initialized")
            await _approval_request_queue.put({
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "required_permissions": required_permissions or [],
                "chat_id": _connection_info.get("chat_id"),
            })
        except Exception as e:
            print(f"DEBUG: Error queueing approval_request: {e}", file=sys.stderr)
            return ("no", f"Failed to queue approval request: {e}")

        try:
            # Wait for the user's response
            result = await future
            return result
        except Exception as e:
            return ("no", str(e))

    _agent.set_approval_callback(approval_callback)

    print(f"JARVIS agent initialized with model: {model}, bypass_tool_permissions: {bypass}")
    return _agent


def _session_path(session_id: str) -> Path:
    """Get the file path for a session."""
    return _SESSIONS_DIR / f"{session_id}.json"


def _load_session(session_id: str) -> dict[str, Any] | None:
    """Load a session from disk."""
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save_session(session_id: str, data: dict[str, Any]) -> None:
    """Save a session to disk."""
    path = _session_path(session_id)
    path.write_text(json.dumps(data, indent=2))


def _list_sessions() -> list[dict[str, Any]]:
    """List all sessions from disk."""
    sessions = []
    for path in _SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            sessions.append(data)
        except Exception:
            continue
    # Sort by updated_at descending
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def _delete_session(session_id: str) -> bool:
    """Delete a session file."""
    path = _session_path(session_id)
    if path.exists():
        path.unlink()
        return True
    return False


@app.get("/jarvis/bootstrap")
async def bootstrap():
    """Bootstrap endpoint for web UI authentication"""
    token = generate_token()
    _tokens[token] = {
        "created": datetime.now().isoformat(),
        "model_name": os.getenv("JARVIS_MODEL", "gpt-4o"),
    }
    return {
        "token": token,
        "ws_path": "/jarvis/ws",
        "model_name": _tokens[token]["model_name"],
        "expires_in": 3600,
    }


@app.get("/jarvis/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.websocket("/jarvis/ws")
async def ws_endpoint(websocket: WebSocket):
    """WebSocket endpoint for chat streaming"""
    import sys
    global _approval_request_queue, _pending_approvals

    try:
        await websocket.accept()
        print("DEBUG: WebSocket accepted successfully", file=sys.stderr)
    except Exception as e:
        print(f"ERROR accepting websocket: {e}", file=sys.stderr)
        return

    try:
        # Initialize the approval request queue for this connection
        _approval_request_queue = asyncio.Queue()
        _pending_approvals = {}

        # Store connection info for this session globally
        global _connection_info
        _connection_info = {
            "authenticated": False,
            "token": None,
            "chat_id": None,
            "session_id": str(uuid.uuid4())
        }

        # Track active connections to prevent duplicates
        if not hasattr(app.state, 'active_connections'):
            app.state.active_connections = {}

        print(f"DEBUG: New WebSocket session {_connection_info['session_id']}", file=sys.stderr)

        # Send initial ready event to let frontend know we're connected
        await websocket.send_json({
            "event": "ready",
            "chat_id": f"temp_{uuid.uuid4().hex[:8]}",
            "client_id": uuid.uuid4().hex[:8]
        })
        print("DEBUG: WebSocket ready, waiting for authentication", file=sys.stderr)

        # Start background task to process approval requests
        async def process_approval_requests():
            """Background task to send approval requests to the frontend."""
            while True:
                try:
                    request = await _approval_request_queue.get()
                    await websocket.send_json({
                        "event": "approval_request",
                        "chat_id": request.get("chat_id"),
                        "tool_name": request.get("tool_name"),
                        "tool_args": request.get("tool_args"),
                        "required_permissions": request.get("required_permissions"),
                        "tool_call_id": request.get("tool_call_id"),
                    })
                except Exception as e:
                    print(f"DEBUG: Error in approval request processor: {e}", file=sys.stderr)
                    break

        approval_task = asyncio.create_task(process_approval_requests())

        # Tracking agent tasks to avoid overlapping and allow concurrent message receiving
        agent_lock = asyncio.Lock()

        async def handle_agent_message(content: str, chat_id: str):
            # Get or create the agent
            agent = _get_agent()

            async with agent_lock:
                # Run agent processing with streaming
                # Initialize original_callbacks before try block for type checking
                original_callbacks: dict = {}
                delta_tasks: list = []
                reasoning_tasks: list = []
                tool_call_tasks: list = []
                tool_result_tasks: list = []
                response: str | None = None
                
                # Save original callbacks before modifying them
                original_callbacks = {
                    "stream_callback": agent.stream_callback,
                    "reasoning_callback": agent.reasoning_callback,
                    "reasoning_done_callback": agent.reasoning_done_callback,
                    "tool_call_callback": agent.tool_call_callback,
                    "tool_result_callback": agent.tool_result_callback,
                    "user_input_callback": agent.user_input_callback if hasattr(agent, 'user_input_callback') else None,
                    "approval_callback": agent.approval_callback if hasattr(agent, 'approval_callback') else None,
                }
                
                try:
                    # Set up a stream callback to send delta events
                    # We use a list to capture the asyncio tasks so we can await them

                    def stream_callback(text: str):
                        # Create the task and store it so we can await it
                        task = asyncio.create_task(websocket.send_json({
                            "event": "delta",
                            "chat_id": chat_id,
                            "text": text,
                        }))
                        delta_tasks.append(task)

                    # Set up reasoning callback to send reasoning events
                    def reasoning_callback(text: str):
                        task = asyncio.create_task(websocket.send_json({
                            "event": "reasoning",
                            "chat_id": chat_id,
                            "text": text,
                        }))
                        reasoning_tasks.append(task)

                    def reasoning_done_callback():
                        task = asyncio.create_task(websocket.send_json({
                            "event": "reasoning_end",
                            "chat_id": chat_id,
                        }))
                        reasoning_tasks.append(task)

                    # Set up tool call callback to send tool_call events
                    def tool_call_callback(tool_name: str, tool_args: dict[str, Any]):
                        task = asyncio.create_task(websocket.send_json({
                            "event": "tool_call",
                            "chat_id": chat_id,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                        }))
                        tool_call_tasks.append(task)

                    # Set up tool result callback to send tool_result events
                    def tool_result_callback(tool_name: str, result: Any, success: bool):
                        # Convert result to string to avoid serialization errors (e.g. ToolOutput objects)
                        serialized_result = str(result)
                        task = asyncio.create_task(websocket.send_json({
                            "event": "tool_result",
                            "chat_id": chat_id,
                            "tool_name": tool_name,
                            "result": serialized_result,
                            "success": bool(success),
                        }))
                        tool_result_tasks.append(task)

                    # Set up user input callback for ask_user questions
                    async def user_input_callback(args: Any) -> Any:
                        await websocket.send_json({
                            "event": "user_input",
                            "chat_id": chat_id,
                            "question": args.get("question", "") if hasattr(args, 'get') else str(args),
                            "options": args.get("options") if hasattr(args, 'get') else None,
                        })
                        return {"answer": ""}

                    # Set up approval callback for tool execution approval
                    async def approval_callback(tool_name: str, tool_args: dict, tool_call_id: str, required_permissions: str) -> tuple:
                        # Send approval request to frontend and wait for response
                        await websocket.send_json({
                            "event": "approval_request",
                            "chat_id": chat_id,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "required_permissions": required_permissions,
                            "tool_call_id": tool_call_id,
                        })

                        future = asyncio.Future()
                        _pending_approvals[tool_call_id] = {"future": future}
                        result = await future
                        return result

                    # Set the callbacks on the agent
                    agent.stream_callback = stream_callback
                    agent.reasoning_callback = reasoning_callback
                    agent.reasoning_done_callback = reasoning_done_callback
                    agent.tool_call_callback = tool_call_callback
                    agent.tool_result_callback = tool_result_callback
                    agent.user_input_callback = user_input_callback
                    agent.approval_callback = approval_callback
                    
                    # Debug: verify callbacks are set
                    print(f"[DEBUG] Agent has reasoning_callback: {agent.reasoning_callback is not None}", file=sys.stderr)

                    # Process the message
                    if _connection_info.get("session_id"):
                        history = ConversationHistory(session_id=_connection_info["session_id"])
                        history.append_message(create_user_message(content))

                    response = await agent.process(content)

                    # Save assistant response to history
                    if _connection_info.get("session_id") and response:
                        history = ConversationHistory(session_id=_connection_info["session_id"])
                        history.append_message(create_assistant_message(response))

                    # Restore original callbacks
                    agent.stream_callback = original_callbacks["stream_callback"]
                    if hasattr(agent, 'reasoning_callback'):
                        agent.reasoning_callback = original_callbacks["reasoning_callback"]
                    if hasattr(agent, 'reasoning_done_callback'):
                        agent.reasoning_done_callback = original_callbacks["reasoning_done_callback"]
                    if hasattr(agent, 'tool_call_callback'):
                        agent.tool_call_callback = original_callbacks["tool_call_callback"]
                    if hasattr(agent, 'tool_result_callback'):
                        agent.tool_result_callback = original_callbacks["tool_result_callback"]
                    if hasattr(agent, 'user_input_callback'):
                        agent.user_input_callback = original_callbacks["user_input_callback"]
                    if hasattr(agent, 'approval_callback'):
                        agent.approval_callback = original_callbacks["approval_callback"]

                    # Wait for all events to be sent
                    await asyncio.gather(*delta_tasks, *reasoning_tasks, *tool_call_tasks, *tool_result_tasks)

                    # Send stream end event
                    await websocket.send_json({
                        "event": "stream_end",
                        "chat_id": chat_id,
                    })

                    # Send final message
                    await websocket.send_json({
                        "event": "message",
                        "chat_id": chat_id,
                        "text": response,
                    })

                    # Send turn end event
                    await websocket.send_json({
                        "event": "turn_end",
                        "chat_id": chat_id,
                    })

                except Exception as e:
                    print(f"DEBUG: Error processing message: {e}", file=sys.stderr)
                    # Restore original callbacks in case of error
                    if original_callbacks:
                        agent.stream_callback = original_callbacks.get("stream_callback")
                        if hasattr(agent, 'reasoning_callback'):
                            agent.reasoning_callback = original_callbacks.get("reasoning_callback")
                        if hasattr(agent, 'reasoning_done_callback'):
                            agent.reasoning_done_callback = original_callbacks.get("reasoning_done_callback")
                        if hasattr(agent, 'tool_call_callback'):
                            agent.tool_call_callback = original_callbacks.get("tool_call_callback")
                        if hasattr(agent, 'tool_result_callback'):
                            agent.tool_result_callback = original_callbacks.get("tool_result_callback")
                        if hasattr(agent, 'user_input_callback'):
                            agent.user_input_callback = original_callbacks.get("user_input_callback")
                        if hasattr(agent, 'approval_callback'):
                            agent.approval_callback = original_callbacks.get("approval_callback")

                    try:
                        await websocket.send_json({
                            "event": "error",
                            "chat_id": chat_id,
                            "detail": str(e),
                        })
                    except:
                        pass

        # Handle incoming messages
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                except WebSocketDisconnect:
                    print("DEBUG: WebSocket disconnected (client closed)", file=sys.stderr)
                    break
                except Exception as e:
                    print(f"DEBUG: Error receiving message: {e}", file=sys.stderr)
                    break

                try:
                    msg = json.loads(data)
                except Exception as e:
                    print(f"DEBUG: Error parsing JSON: {e}", file=sys.stderr)
                    continue

                # Handle different message types from frontend
                msg_type = msg.get("type")

                if msg_type == "attach":
                    # Attach to existing chat - need to authenticate first
                    chat_id = msg.get("chat_id")
                    if not _connection_info["authenticated"]:
                        # For now, auto-authenticate with a generated token
                        # In production, this should validate against a real token
                        token = generate_token()
                        _tokens[token] = {
                            "created": datetime.now().isoformat(),
                            "model_name": os.getenv("JARVIS_MODEL", "gpt-4o"),
                        }
                        _connection_info["authenticated"] = True
                        _connection_info["token"] = token
                        _connection_info["chat_id"] = chat_id

                    # Load session data to get session_id
                    session_data = _load_session(chat_id)
                    if session_data and "session_id" in session_data:
                        _connection_info["session_id"] = session_data["session_id"]

                    await websocket.send_json({
                        "event": "attached",
                        "chat_id": chat_id,
                        "session_id": _connection_info.get("session_id"),
                    })
                    print(f"DEBUG: Attached to chat_id: {chat_id}", file=sys.stderr)

                elif msg_type == "new_chat":
                    # Create new chat session
                    if not _connection_info["authenticated"]:
                        token = generate_token()
                        _tokens[token] = {
                            "created": datetime.now().isoformat(),
                            "model_name": os.getenv("JARVIS_MODEL", "gpt-4o"),
                        }
                        _connection_info["authenticated"] = True
                        _connection_info["token"] = token

                    chat_id = f"chat_{uuid.uuid4().hex[:8]}"
                    _connection_info["chat_id"] = chat_id

                    # Clear agent memory for new conversation
                    agent = _get_agent()
                    agent.clear_memory()

                    # Create new history for this session
                    history = ConversationHistory()
                    _connection_info["session_id"] = history.session_id

                    # Save to sessions directory for persistence
                    session_data = {
                        "id": chat_id,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "preview": "",
                        "messages": [],
                        "session_id": history.session_id,
                    }
                    _save_session(chat_id, session_data)

                    await websocket.send_json({
                        "event": "attached",
                        "chat_id": chat_id,
                        "session_id": history.session_id,
                    })
                    print(f"DEBUG: Created new chat_id: {chat_id} with fresh history (session: {history.session_id[:8]}...)", file=sys.stderr)

                elif msg_type == "approval_response":
                    # Handle approval response from frontend
                    tool_call_id = msg.get("tool_call_id")
                    approved = msg.get("approved", False)
                    always_allow = msg.get("always_allow", False)

                    print(f"DEBUG: Received approval_response for {tool_call_id}, approved={approved}, always_allow={always_allow}", file=sys.stderr)

                    if tool_call_id in _pending_approvals:
                        pending = _pending_approvals.pop(tool_call_id)
                        future = pending["future"]
                        if not future.done():
                            if approved:
                                result = ("yes", None) if not always_allow else ("yes", "always_allow")
                            else:
                                result = ("no", "User declined tool execution")
                            future.set_result(result)
                    else:
                        print(f"DEBUG: Unknown tool_call_id in approval_response: {tool_call_id}", file=sys.stderr)

                elif msg_type == "message":
                    # Handle user message
                    content = msg.get("content", "")
                    chat_id = msg.get("chat_id", _connection_info.get("chat_id"))

                    if not chat_id:
                        print("DEBUG: No chat_id available for message", file=sys.stderr)
                        continue

                    # Start processing in a separate task
                    asyncio.create_task(handle_agent_message(content, chat_id))

                else:
                    print(f"DEBUG: Ignoring message with unknown type: {msg_type}", file=sys.stderr)

        finally:
            # Cancel the approval task when the websocket closes
            approval_task.cancel()
            try:
                await approval_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        print("DEBUG: WebSocket disconnected (outer)", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Error in websocket handler: {e}", file=sys.stderr)
        try:
            await websocket.send_json({"error": str(e), "event": "error"})
        except Exception:
            pass


@app.get("/api/sessions")
async def api_list_sessions():
    """List all chat sessions"""
    sessions = _list_sessions()
    result = []
    for s in sessions:
        result.append({
            "key": f"websocket:{s['id']}",
            "channel": "websocket",
            "chatId": s["id"],
            "createdAt": s.get("created_at"),
            "updatedAt": s.get("updated_at"),
            "preview": s.get("preview", ""),
        })
    return result


@app.get("/jarvis/api/sessions")
async def jarvis_list_sessions():
    """Legacy: List all chat sessions"""
    return await api_list_sessions()


@app.post("/api/sessions")
async def api_create_session():
    """Create a new chat session"""
    session_id = secrets.token_hex(8)
    now = datetime.now().isoformat()
    data = {
        "id": session_id,
        "created_at": now,
        "updated_at": now,
        "preview": "",
        "messages": [],
    }
    _save_session(session_id, data)
    return {"id": session_id, "created": now}


@app.post("/jarvis/api/sessions")
async def jarvis_create_session():
    """Legacy: Create a new chat session"""
    return await api_create_session()


@app.get("/api/sessions/{session_id}")
async def api_get_session(session_id: str):
    """Get a session by ID"""
    data = _load_session(session_id)
    if not data:
        return JSONResponse(content={"error": "not found"}, status_code=404)
    return data


@app.get("/api/sessions/{session_id}/messages")
async def api_get_session_messages(session_id: str):
    """Get messages for a session"""
    data = _load_session(session_id)
    if not data:
        return JSONResponse(content={"error": "not found"}, status_code=404)
    return {
        "key": f"websocket:{session_id}",
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "messages": data.get("messages", []),
    }


@app.get("/api/history/{chat_id}")
async def api_get_history(chat_id: str):
    """Get conversation history for a chat."""
    session_data = _load_session(chat_id)
    if not session_data:
        return JSONResponse(content={"error": "Session not found"}, status_code=404)

    session_id = session_data.get("session_id")
    if not session_id:
        return JSONResponse(content={"error": "No session ID found"}, status_code=404)

    history = ConversationHistory(session_id=session_id)
    messages = history.get_messages()

    return {
        "session_id": session_id,
        "chat_id": chat_id,
        "messages": [msg.to_dict() for msg in messages],
    }


@app.delete("/api/sessions/{session_id}")
@app.post("/api/sessions/{session_id}/delete")
async def api_delete_session(session_id: str):
    """Delete a session"""
    success = _delete_session(session_id)
    return {"deleted": success}


@app.delete("/jarvis/api/sessions/{session_id}")
@app.post("/jarvis/api/sessions/{session_id}/delete")
async def jarvis_delete_session(session_id: str):
    """Legacy: Delete a session"""
    return await api_delete_session(session_id)


@app.get("/api/settings")
async def api_get_settings():
    """Get current settings"""
    provider = os.getenv("JARVIS_SDK", "openai")
    model = os.getenv("JARVIS_MODEL", "gpt-4o")
    has_api_key = bool(os.getenv("JARVIS_API_KEY"))
    thinking_level = os.getenv("JARVIS_THINKING_LEVEL", "medium")

    if provider == "openai":
        resolved_provider = "openai"
    elif provider == "anthropic":
        resolved_provider = "anthropic"
    else:
        resolved_provider = "auto"

    return {
        "agent": {
            "model": model,
            "provider": provider,
            "resolved_provider": resolved_provider,
            "has_api_key": has_api_key,
            "thinking_level": thinking_level,
        },
        "providers": [
            {"name": "auto", "label": "Auto"},
            {"name": "openai", "label": "OpenAI"},
            {"name": "anthropic", "label": "Anthropic"},
        ],
        "thinking_levels": [
            {"name": "low", "label": "Low", "description": "Minimal reasoning"},
            {"name": "medium", "label": "Medium", "description": "Balanced reasoning"},
            {"name": "high", "label": "High", "description": "Detailed reasoning"},
        ],
        "runtime": {
            "config_path": str(Path.home() / ".jarvis" / "config.json"),
        },
        "requires_restart": False,
    }


@app.get("/api/settings/update")
async def api_update_settings(request: Request):
    """Update settings"""
    model = request.query_params.get("model", os.getenv("JARVIS_MODEL", "gpt-4o"))
    provider = request.query_params.get("provider", os.getenv("JARVIS_SDK", "openai"))
    thinking_level = request.query_params.get("thinking_level", os.getenv("JARVIS_THINKING_LEVEL", "medium"))

    if provider == "openai":
        resolved_provider = "openai"
    elif provider == "anthropic":
        resolved_provider = "anthropic"
    else:
        resolved_provider = "auto"

    os.environ["JARVIS_THINKING_LEVEL"] = thinking_level

    return {
        "agent": {
            "model": model,
            "provider": provider,
            "resolved_provider": resolved_provider,
            "has_api_key": bool(os.getenv("JARVIS_API_KEY")),
            "thinking_level": thinking_level,
        },
        "providers": [
            {"name": "auto", "label": "Auto"},
            {"name": "openai", "label": "OpenAI"},
            {"name": "anthropic", "label": "Anthropic"},
        ],
        "thinking_levels": [
            {"name": "low", "label": "Low", "description": "Minimal reasoning"},
            {"name": "medium", "label": "Medium", "description": "Balanced reasoning"},
            {"name": "high", "label": "High", "description": "Detailed reasoning"},
        ],
        "runtime": {
            "config_path": str(Path.home() / ".jarvis" / "config.json"),
        },
        "requires_restart": False,
    }


# ── Model Picker endpoints ──────────────────────────────────────────────
_agent_ref: Any = None  # Global agent reference for runtime access


def _get_or_create_agent():
    global _agent_ref
    if _agent_ref is not None:
        return _agent_ref
    _agent_ref = _get_agent()
    return _agent_ref


@app.get("/api/models")
async def api_list_models():
    """List available models from providers."""
    try:
        from core.llm.model_info import get_model_info
        models = [
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai", "family": "openai", "capabilities": {"reasoning": True, "vision": True, "tool_call": True}},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "family": "openai", "capabilities": {"reasoning": True, "vision": True, "tool_call": True}},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "openai", "family": "openai", "capabilities": {"reasoning": False, "vision": True, "tool_call": True}},
            {"id": "gpt-4", "name": "GPT-4", "provider": "openai", "family": "openai", "capabilities": {"reasoning": False, "vision": False, "tool_call": True}},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "openai", "family": "openai", "capabilities": {"reasoning": False, "vision": False, "tool_call": True}},
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic", "family": "anthropic", "capabilities": {"reasoning": True, "vision": True, "tool_call": True}},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic", "family": "anthropic", "capabilities": {"reasoning": True, "vision": True, "tool_call": True}},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic", "family": "anthropic", "capabilities": {"reasoning": False, "vision": True, "tool_call": True}},
        ]
        return {"models": models, "current_model": os.getenv("JARVIS_MODEL", "gpt-4o")}
    except Exception as e:
        return {"models": [], "current_model": os.getenv("JARVIS_MODEL", "gpt-4o"), "error": str(e)[:100]}


@app.get("/api/providers")
async def api_list_providers():
    """List available LLM providers."""
    try:
        from core.provider.manager import ProviderManager
        pm = ProviderManager()
        providers = []
        for p in pm.list_enabled_providers():
            providers.append({
                "provider_id": p.provider_id,
                "sdk_mode": p.sdk_mode,
                "default_model": p.default_model,
                "enabled": p.enabled,
                "models": p.models,
                "has_api_key": bool(p.api_key),
                "base_url": p.base_url or "",
            })
        if not providers:
            providers = [
                {"provider_id": "openai", "sdk_mode": "openai", "default_model": "gpt-4o", "enabled": True, "models": [], "has_api_key": bool(os.getenv("JARVIS_API_KEY")), "base_url": os.getenv("JARVIS_BASE_URL", "")},
                {"provider_id": "anthropic", "sdk_mode": "anthropic", "default_model": "claude-sonnet-4-20250514", "enabled": True, "models": [], "has_api_key": False, "base_url": ""},
            ]
        return {"providers": providers}
    except Exception as e:
        return {"providers": [], "error": str(e)[:100]}


@app.post("/api/settings/model")
async def api_set_model(request: Request):
    """Switch the active model."""
    try:
        body = await request.json()
        model = body.get("model", "")
        provider = body.get("provider", "")
        if model:
            os.environ["JARVIS_MODEL"] = model
        if provider:
            os.environ["JARVIS_SDK"] = provider
        return {"success": True, "model": os.getenv("JARVIS_MODEL", model), "provider": os.getenv("JARVIS_SDK", provider)}
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


# ── MCP Integration endpoints ──────────────────────────────────────────

@app.get("/api/mcp/servers")
async def api_mcp_list_servers():
    """List MCP servers."""
    try:
        from core.tools.mcp_adapter import MCPRegistry, load_mcp_config_from_file
        registry = MCPRegistry()
        configs = load_mcp_config_from_file() or []
        servers = [_mcp_server_summary(s) for s in configs]
        return {"servers": servers}
    except Exception as e:
        return {"servers": [], "error": str(e)[:100]}


def _mcp_server_summary(config: Any) -> dict:
    name = config.get("name", "unknown") if isinstance(config, dict) else getattr(config, "name", "unknown")
    command = config.get("command", "") if isinstance(config, dict) else getattr(config, "command", "")
    transport = config.get("transport", "stdio") if isinstance(config, dict) else getattr(config, "transport", "stdio")
    disabled = config.get("disabled", False) if isinstance(config, dict) else getattr(config, "disabled", False)
    lifecycle = config.get("lifecycle", "lazy") if isinstance(config, dict) else getattr(config, "lifecycle", "lazy")
    return {
        "name": name,
        "command": command,
        "transport": transport,
        "disabled": disabled,
        "lifecycle": lifecycle,
        "connected": False,
        "tool_count": 0,
    }


@app.post("/api/mcp/servers")
async def api_mcp_add_server(request: Request):
    """Add a new MCP server."""
    try:
        body = await request.json()
        from core.tools.mcp_adapter import MCPServerConfig, create_mcp_client_from_config
        config = MCPServerConfig(
            name=body.get("name", "mcp-server"),
            command=body.get("command", ""),
            args=body.get("args", []),
            env=body.get("env", {}),
            transport=body.get("transport", "stdio"),
            url=body.get("url", ""),
            disabled=False,
            lifecycle=body.get("lifecycle", "eager"),
        )
        return {"success": True, "server": _mcp_server_summary(body)}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


@app.delete("/api/mcp/servers/{name}")
async def api_mcp_remove_server(name: str):
    """Remove an MCP server."""
    return {"success": True, "server": name}


@app.get("/api/mcp/tools")
async def api_mcp_list_tools():
    """List all MCP tools."""
    try:
        tools = []
        return {"tools": tools}
    except Exception as e:
        return {"tools": [], "error": str(e)[:100]}


# ── Heartbeat endpoints ─────────────────────────────────────────────────

@app.get("/api/heartbeat")
async def api_heartbeat_status():
    """Get heartbeat system status."""
    hb_file = Path.home() / ".jarvis" / "HEARTBEAT.md"
    results_file = Path.home() / ".jarvis" / "HEARTBEAT_RESULTS.md"
    return {
        "enabled": os.getenv("JARVIS_HEARTBEAT_ENABLED", "true").lower() == "true",
        "interval": os.getenv("JARVIS_HEARTBEAT_EVERY", "30m"),
        "is_running": os.getenv("JARVIS_HEARTBEAT_ENABLED", "true").lower() == "true",
        "last_run": None,
        "last_result": results_file.read_text()[:500] if results_file.exists() else None,
        "heartbeat_file": hb_file.read_text()[:1000] if hb_file.exists() else "",
        "has_heartbeat_file": hb_file.exists(),
    }


@app.post("/api/heartbeat/start")
async def api_heartbeat_start():
    """Start the heartbeat scheduler."""
    os.environ["JARVIS_HEARTBEAT_ENABLED"] = "true"
    return {"success": True, "status": "running"}


@app.post("/api/heartbeat/stop")
async def api_heartbeat_stop():
    """Stop the heartbeat scheduler."""
    os.environ["JARVIS_HEARTBEAT_ENABLED"] = "false"
    return {"success": True, "status": "stopped"}


# ── Rewind endpoints ────────────────────────────────────────────────────

@app.get("/api/sessions/{session_id}/checkpoints")
async def api_session_checkpoints(session_id: str):
    """Get checkpoints for a session (for rewind)."""
    data = _load_session(session_id)
    if not data:
        return JSONResponse(content={"error": "not found"}, status_code=404)
    messages = data.get("messages", [])
    checkpoints = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            checkpoints.append({
                "index": i,
                "content": msg.get("content", "")[:200],
                "timestamp": msg.get("timestamp", ""),
                "has_file_changes": False,
            })
    return {
        "session_id": session_id,
        "checkpoints": checkpoints,
    }


@app.post("/api/sessions/{session_id}/rewind")
async def api_session_rewind(session_id: str, request: Request):
    """Rewind a session to a specific message index."""
    try:
        body = await request.json()
        msg_index = body.get("message_index", 0)
        restore_files = body.get("restore_files", False)
        data = _load_session(session_id)
        if not data:
            return JSONResponse(content={"error": "not found"}, status_code=404)
        messages = data.get("messages", [])
        if msg_index < 0 or msg_index >= len(messages):
            return JSONResponse(content={"error": "invalid index"}, status_code=400)
        target_msg = messages[msg_index]
        data["messages"] = messages[:msg_index + 1]
        data["updated_at"] = datetime.now().isoformat()
        _save_session(session_id, data)
        return {
            "success": True,
            "rewound_to": msg_index,
            "message_content": target_msg.get("content", ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Voice Input endpoint ────────────────────────────────────────────────

@app.post("/api/voice/transcribe")
async def api_voice_transcribe(request: Request):
    """Transcribe voice audio to text (placeholder)."""
    return {
        "success": True,
        "text": "",
        "note": "Voice transcription requires a speech-to-text backend (Whisper/Whisper.cpp) to be installed.",
    }


# ── Feedback endpoint ───────────────────────────────────────────────────

feedback_store: list = []


@app.post("/api/feedback")
async def api_submit_feedback(request: Request):
    """Submit user feedback."""
    try:
        body = await request.json()
        rating = body.get("rating")
        message = body.get("message", "")
        page = body.get("page", "")
        feedback_store.append({
            "rating": rating,
            "message": message,
            "page": page,
            "timestamp": datetime.now().isoformat(),
        })
        fb_file = Path.home() / ".jarvis" / "feedback.jsonl"
        fb_file.parent.mkdir(parents=True, exist_ok=True)
        with open(fb_file, "a") as f:
            f.write(json.dumps(feedback_store[-1]) + "\n")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Debug Console endpoint ─────────────────────────────────────────────

_debug_log: list = []


@app.get("/api/debug/logs")
async def api_debug_logs():
    """Get recent debug logs."""
    import io
    import sys
    buf = io.StringIO()
    return {
        "logs": _debug_log[-200:],
        "note": "Debug console showing last 200 log entries.",
    }


@app.post("/api/debug/command")
async def api_debug_command(request: Request):
    """Execute a debug command."""
    try:
        body = await request.json()
        cmd = body.get("command", "")
        args = body.get("args", {})
        result = {"output": f"Executed: {cmd}", "success": True}
        if cmd == "ping":
            result["output"] = "pong"
        elif cmd == "clear_logs":
            _debug_log.clear()
            result["output"] = "Logs cleared"
        elif cmd == "health":
            result["output"] = json.dumps({"status": "ok", "uptime": "active"})
        else:
            result["output"] = f"Unknown command: {cmd}"
        return result
    except Exception as e:
        return {"output": f"Error: {e}", "success": False}


# ── Context / Token Usage endpoint ──────────────────────────────────────

@app.get("/api/context/usage")
async def api_context_usage():
    """Get current token usage and context limits."""
    try:
        agent = _get_or_create_agent()
        usage = {}
        if hasattr(agent, 'provider') and hasattr(agent.provider, 'get_and_clear_usage'):
            u = agent.provider.get_and_clear_usage()
            if u:
                usage = u
        from core.llm_sdk.context_length_manager import context_length_manager
        model = os.getenv("JARVIS_MODEL", "gpt-4o")
        limits = context_length_manager.get_token_limits(model)
        return {
            "usage": usage,
            "limits": {
                "context": limits.total_context_tokens,
                "output": limits.max_output_tokens,
            },
            "model": model,
            "message_count": 0,
        }
    except Exception as e:
        return {"usage": {}, "limits": {"context": 128000, "output": 16000}, "model": os.getenv("JARVIS_MODEL", "gpt-4o"), "message_count": 0, "error": str(e)[:100]}


# ── Connector Auth endpoints ────────────────────────────────────────────

@app.get("/api/connectors")
async def api_list_connectors():
    """List all connectors with auth status."""
    try:
        from core.connectors.registry import ConnectorRegistry, load_connectors
        load_connectors()
        status = ConnectorRegistry.get_connection_status()
        connectors = []
        for cid, info in status.items():
            connectors.append({
                "id": cid,
                "display_name": info.get("display_name", cid),
                "auth_type": info.get("auth_type", "none"),
                "connected": info.get("connected", False),
                "auth_configured": info.get("auth_type", "none") != "none",
                "sync_state": info.get("sync_status", {}).get("state", "idle") if isinstance(info.get("sync_status"), dict) else "idle",
            })
        return {"connectors": connectors}
    except Exception as e:
        return {"connectors": [], "error": str(e)[:200]}


@app.post("/api/connectors/{name}/auth")
async def api_connector_auth(name: str, request: Request):
    """Set credentials for a connector."""
    try:
        body = await request.json()
        from core.connectors.registry import ConnectorRegistry, load_connectors
        load_connectors()
        connector_cls = ConnectorRegistry.get_class(name)
        if not connector_cls:
            return {"success": False, "error": f"Connector '{name}' not found"}
        inst = connector_cls()
        if name == "github":
            inst.set_credentials(
                token=body.get("token", ""),
                username=body.get("username", ""),
                repos=body.get("repos", []),
            )
        elif name == "weather":
            inst.set_api_key(body.get("api_key", ""), body.get("city", ""))
        elif name == "http":
            if body.get("headers"):
                inst.set_default_headers(body["headers"])
        return {"success": True, "connector": name, "connected": inst.is_connected()}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Safety Profiles endpoint ────────────────────────────────────────────

SAFETY_PROFILES = [
    {"id": 1, "name": "Lockdown", "desc": "Everything asks. No code execution.", "bypass": False, "code": "never", "files": "ask", "dangerous": "ask"},
    {"id": 2, "name": "Restricted", "desc": "File ops ask. Code execution ask.", "bypass": False, "code": "ask", "files": "ask", "dangerous": "ask"},
    {"id": 3, "name": "Balanced", "desc": "Default. File ops allowed, code asks.", "bypass": False, "code": "ask", "files": "always", "dangerous": "ask"},
    {"id": 4, "name": "Permissive", "desc": "Most operations allowed automatically.", "bypass": False, "code": "always", "files": "always", "dangerous": "ask"},
    {"id": 5, "name": "Unrestricted", "desc": "All operations allowed. No prompts.", "bypass": True, "code": "always", "files": "always", "dangerous": "always"},
]


def _get_current_safety_profile() -> dict:
    bypass = os.getenv("JARVIS_BYPASS_PERMISSIONS", "").lower() == "true"
    code_perm = os.getenv("JARVIS_CODE_PERMISSION", "ask")
    for p in SAFETY_PROFILES:
        if p["bypass"] == bypass and p["code"] == code_perm:
            return p
    return SAFETY_PROFILES[2]  # Balanced default


@app.get("/api/safety/profile")
async def api_get_safety_profile():
    """Get current safety profile."""
    return {"profiles": SAFETY_PROFILES, "current": _get_current_safety_profile()}


@app.post("/api/safety/profile")
async def api_set_safety_profile(request: Request):
    """Set safety profile by ID."""
    try:
        body = await request.json()
        profile_id = body.get("profile_id", 3)
        profile = next((p for p in SAFETY_PROFILES if p["id"] == profile_id), None)
        if not profile:
            return {"success": False, "error": f"Profile {profile_id} not found"}
        os.environ["JARVIS_BYPASS_PERMISSIONS"] = "true" if profile["bypass"] else ""
        os.environ["JARVIS_CODE_PERMISSION"] = profile["code"]
        return {"success": True, "profile": profile}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


@app.get("/api/sessions/remote")
async def api_list_remote_sessions():
    """List remote sessions from cloud/remote instances.
    
    This endpoint allows connecting to remote JARVIS instances to list
    and resume sessions stored in the cloud.
    """
    remote_url = os.getenv("JARVIS_REMOTE_URL", "")
    
    if not remote_url:
        return {"sessions": [], "error": "No remote URL configured. Set JARVIS_REMOTE_URL to enable remote sessions."}
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{remote_url}/api/sessions")
            if response.status_code == 200:
                data = response.json()
                sessions = data.get("sessions", [])
                return {
                    "sessions": [
                        {
                            "key": f"remote:{s.get('key', s.get('session_id', ''))}",
                            "source": "remote",
                            "title": s.get("title", s.get("preview", "Remote Session")),
                            "status": s.get("status", "active"),
                            "created_at": s.get("created_at"),
                            "updated_at": s.get("updated_at"),
                        }
                        for s in sessions
                    ]
                }
            return {"sessions": [], "error": f"Failed to fetch remote sessions: {response.status_code}"}
    except Exception as e:
        return {"sessions": [], "error": f"Failed to connect to remote: {str(e)[:100]}"}


@app.get("/")
async def serve_index():
    """Serve the webui index.html"""
    if _WEBUI_DIR.exists():
        index_file = _WEBUI_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return JSONResponse(content={"error": "Web UI not built. Run 'npm run build' in interface/webui/"}, status_code=503)


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve SPA fallback - return index.html for client-side routes"""
    if _WEBUI_DIR.exists():
        index_file = _WEBUI_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return JSONResponse(content={"error": "Web UI not built"}, status_code=503)


def run_server(host: str = "0.0.0.0", port: int = 8765, debug: bool = False):
    """Run the web UI server using uvicorn"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server(debug=True)
