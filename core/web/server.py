"""Web UI API server for JARVIS using FastAPI"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent instance for WebSocket chat
_agent: Any = None

# In-memory token store (in production, use Redis or similar)
_tokens: dict = {}

# Session storage directory
_SESSIONS_DIR = Path.home() / ".jarvis" / "sessions"
_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def _get_agent():
    """Get or create the JARVIS agent instance."""
    global _agent
    
    if _agent is not None:
        return _agent
    
    # Import here to avoid circular imports
    from core.agents.coding_agent import CodingAgent
    from core.llm.sdk_adapter import SDKAdapter
    from core.llm_sdk.openai.sdk import OpenAISDK
    from core.llm_sdk.anthropic.sdk import AnthropicSDK
    from core.tools.registry import ToolRegistry
    from core.config.settings import Settings
    from core.agents.system_prompts import get_system_context
    
    # Import core tools
    from core.tools.file_tools import FileReadTool, FileWriteTool, FindTool, LSTool
    from core.tools.code_tools import BashTool, RunTestsTool
    from core.tools.grep_tool import GrepSearchTool
    from core.tools.web_tools import WebFetchTool, ExaWebSearchTool
    
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
    tool_registry.register(ExaWebSearchTool())
    
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
    
    print(f"JARVIS agent initialized with model: {model}")
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
    
    try:
        await websocket.accept()
        print(f"DEBUG: WebSocket accepted successfully", file=sys.stderr)
    except Exception as e:
        print(f"ERROR accepting websocket: {e}", file=sys.stderr)
        return
    
    try:
        # Store connection info for this session
        connection_info = {
            "authenticated": False,
            "token": None,
            "chat_id": None
        }
        
        # Send initial ready event to let frontend know we're connected
        await websocket.send_json({
            "event": "ready",
            "chat_id": f"temp_{uuid.uuid4().hex[:8]}",
            "client_id": uuid.uuid4().hex[:8]
        })
        print(f"DEBUG: WebSocket ready, waiting for authentication", file=sys.stderr)
        
        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                print(f"DEBUG: WebSocket disconnected (client closed)", file=sys.stderr)
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
                if not connection_info["authenticated"]:
                    # For now, auto-authenticate with a generated token
                    # In production, this should validate against a real token
                    token = generate_token()
                    _tokens[token] = {
                        "created": datetime.now().isoformat(),
                        "model_name": os.getenv("JARVIS_MODEL", "gpt-4o"),
                    }
                    connection_info["authenticated"] = True
                    connection_info["token"] = token
                    connection_info["chat_id"] = chat_id
                
                await websocket.send_json({
                    "event": "attached",
                    "chat_id": chat_id
                })
                print(f"DEBUG: Attached to chat_id: {chat_id}", file=sys.stderr)
                
            elif msg_type == "new_chat":
                # Create new chat session
                if not connection_info["authenticated"]:
                    token = generate_token()
                    _tokens[token] = {
                        "created": datetime.now().isoformat(),
                        "model_name": os.getenv("JARVIS_MODEL", "gpt-4o"),
                    }
                    connection_info["authenticated"] = True
                    connection_info["token"] = token
                
                chat_id = f"chat_{uuid.uuid4().hex[:8]}"
                connection_info["chat_id"] = chat_id
                
                await websocket.send_json({
                    "event": "attached",
                    "chat_id": chat_id
                })
                print(f"DEBUG: Created new chat_id: {chat_id}", file=sys.stderr)
                
            elif msg_type == "message":
                # Handle user message
                content = msg.get("content", "")
                chat_id = msg.get("chat_id", connection_info.get("chat_id"))
                
                if not chat_id:
                    print(f"DEBUG: No chat_id available for message", file=sys.stderr)
                    continue
                
                # Get or create the agent
                agent = _get_agent()
                
                # Run agent processing with streaming
                try:
                    # Set up a stream callback to send delta events
                    def stream_callback(text: str):
                        # Schedule the async send to avoid blocking
                        asyncio.create_task(websocket.send_json({
                            "event": "delta",
                            "chat_id": chat_id,
                            "text": text,
                        }))
                    
                    # Temporarily set the stream callback
                    original_callback = agent.stream_callback
                    agent.stream_callback = stream_callback
                    
                    # Process the message
                    response = await agent.process(content)
                    
                    # Restore original callback
                    agent.stream_callback = original_callback
                    
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
                    # Restore original callback in case of error
                    if hasattr(agent, 'stream_callback'):
                        agent.stream_callback = original_callback
                    await websocket.send_json({
                        "event": "error",
                        "chat_id": chat_id,
                        "detail": str(e),
                    })
            else:
                print(f"DEBUG: Ignoring message with unknown type: {msg_type}", file=sys.stderr)
    
    except WebSocketDisconnect:
        print(f"DEBUG: WebSocket disconnected (outer)", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Error in websocket handler: {e}", file=sys.stderr)
        try:
            await websocket.send_json({"error": str(e), "event": "error"})
        except Exception:
            pass
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
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
        },
        "providers": [
            {"name": "auto", "label": "Auto"},
            {"name": "openai", "label": "OpenAI"},
            {"name": "anthropic", "label": "Anthropic"},
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
            "has_api_key": bool(os.getenv("JARVIS_API_KEY")),
        },
        "providers": [
            {"name": "auto", "label": "Auto"},
            {"name": "openai", "label": "OpenAI"},
            {"name": "anthropic", "label": "Anthropic"},
        ],
        "runtime": {
            "config_path": str(Path.home() / ".jarvis" / "config.json"),
        },
        "requires_restart": False,
    }


def run_server(host: str = "0.0.0.0", port: int = 8765, debug: bool = False):
    """Run the web UI server using uvicorn"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server(debug=True)