"""Web UI launcher for JARVIS."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.request
import webbrowser
import threading
import time
from pathlib import Path


def main(
    model: str = "gpt-4o",
    base_url: str = "",
    apikey: str = "",
    sdk: str = "openai",
    bypass: bool = False,
    host: str = "127.0.0.1",
    port: int = 5173,
    backend_port: int = 8765,
) -> None:
    """Launch the JARVIS Web UI.

    Args:
        model: Model name to use (e.g., gpt-4o, claude-3-5-sonnet)
        base_url: Base URL for the LLM API
        apikey: API key for the LLM provider
        sdk: SDK mode (openai or anthropic)
        bypass: Bypass all tool permission checks
        host: Host to bind the frontend server to (use 0.0.0.0 for all devices)
        port: Port for the frontend server
        backend_port: Port for the backend server
    """
    # Set environment variables for the web server
    os.environ["JARVIS_MODEL"] = model
    if base_url:
        os.environ["JARVIS_BASE_URL"] = base_url
    if apikey:
        os.environ["JARVIS_API_KEY"] = apikey
    os.environ["JARVIS_SDK"] = sdk
    if bypass:
        os.environ["JARVIS_BYPASS_PERMISSIONS"] = "1"

    # Add project root to path
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Backend server configuration - always bind to 0.0.0.0 for external access
    backend_host = "0.0.0.0"
    # For the frontend to connect to backend, we need to use the actual host
    # If host is 0.0.0.0, we use 127.0.0.1 for the browser connection
    backend_connect_host = "127.0.0.1" if host == "127.0.0.1" else host
    
    # Get the webui directory
    webui_dir = Path(__file__).resolve().parent

    # Start the backend server using uvicorn (FastAPI's native WebSocket support)
    def start_backend():
        import uvicorn
        from core.web.server import app
        
        print(f"Starting JARVIS backend on http://{backend_host}:{backend_port} (uvicorn + fastapi)")
        uvicorn.run(app, host=backend_host, port=backend_port, log_level="info")

    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    # Wait for the backend to be ready with a health check
    backend_url = f"http://{backend_connect_host}:{backend_port}"
    print(f"Waiting for backend server to be ready at {backend_url}...")
    max_retries = 30
    retry_delay = 0.5
    backend_ready = False
    for i in range(max_retries):
        try:
            req = urllib.request.Request(f"{backend_url}/jarvis/health")
            urllib.request.urlopen(req, timeout=2)
            backend_ready = True
            print(f"Backend server is ready!")
            break
        except Exception:
            time.sleep(retry_delay)
    
    if not backend_ready:
        print(f"WARNING: Backend server may not be ready. Proceeding anyway...")

    # Start the frontend dev server (npm run dev)
    # On Windows, we need to use npm.cmd instead of npm
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    
    # Check if node_modules exists
    node_modules = webui_dir / "node_modules"
    if not node_modules.exists():
        print("ERROR: node_modules not found. Please run 'npm install' in the webui directory first.")
        print(f"   cd {webui_dir}")
        print(f"   npm install")
        return
    
    # Check if npm is available
    try:
        subprocess.run([npm_cmd, "--version"], cwd=str(webui_dir), capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: npm is not available: {e}")
        print("Please install Node.js and npm from https://nodejs.org/")
        return
    
    # Set environment variables for the frontend to know where the backend is
    frontend_env = os.environ.copy()
    frontend_env["JARVIS_API_URL"] = f"http://{backend_connect_host}:{backend_port}"
    
    print(f"Starting JARVIS frontend dev server...")
    npm_process = subprocess.Popen(
        [npm_cmd, "run", "dev", "--", "--host", host, "--port", str(port)],
        cwd=str(webui_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=frontend_env
    )
    
    # Read npm output in background to catch any errors
    def read_npm_output():
        if npm_process.stdout:
            for line in npm_process.stdout:
                print(f"   [npm] {line.rstrip()}")
    
    npm_output_thread = threading.Thread(target=read_npm_output, daemon=True)
    npm_output_thread.start()

    # Wait for the frontend server to start
    print("Waiting for frontend dev server to start...")
    max_frontend_retries = 30
    for i in range(max_frontend_retries):
        try:
            req = urllib.request.Request(f"http://{host}:{port}")
            urllib.request.urlopen(req, timeout=2)
            print(f"Frontend dev server is ready!")
            break
        except Exception:
            time.sleep(0.5)
    else:
        print(f"WARNING: Frontend server may not be ready. Proceeding anyway...")

    # Open browser to the frontend URL (use 127.0.0.1 for localhost even if binding to 0.0.0.0)
    frontend_url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"
    print(f"Opening browser at {frontend_url}")
    webbrowser.open(frontend_url)

    # Determine display host for messages
    display_host = "localhost" if host in ("127.0.0.1", "localhost") else host
    
    print(f"\n+ JARVIS Web UI is running!")
    print(f"   Frontend: http://{display_host}:{port}")
    print(f"   Backend:  http://{display_host}:{backend_port}")
    if host == "0.0.0.0":
        print(f"\n   [Network] Accessible from other devices on the network!")
    print("\nPress Ctrl+C to stop all servers")

    try:
        # Wait for the npm process
        npm_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        npm_process.terminate()
        try:
            npm_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            npm_process.kill()
        print("Servers stopped.")


def _parse_args(argv: list[str]) -> tuple[str, int, int]:
    """Parse command-line arguments for webui."""
    parser = argparse.ArgumentParser(
        prog="jarvis --webui",
        description="Launch the JARVIS Web UI"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (use 0.0.0.0 for all devices, default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5173,
        help="Port for the frontend server (default: 5173)"
    )
    parser.add_argument(
        "--backend-port", "-b",
        type=int,
        default=8765,
        help="Port for the backend server (default: 8765)"
    )
    
    args, unknown = parser.parse_known_args(argv)
    return args.host, args.port, args.backend_port


if __name__ == "__main__":
    # Get the additional arguments for webui
    webui_host, webui_port, backend_port = _parse_args(sys.argv[1:])
    
    # We need to filter out the webui-specific args before passing to main
    # The cli.py will call main() directly with model, base_url, etc.
    # So we'll just use the defaults and let cli.py handle the specific args
    main(host=webui_host, port=webui_port, backend_port=backend_port)