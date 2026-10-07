#!/usr/bin/env python3
"""
app.py - MCP Client for lab01-mcp-fundamentals

Interactive MCP Client with real LLM integration (Ollama).

Features:
  - /tools      : List available tools (echo + MCP server tools)
  - /help       : Show help
  - /register   : Register MCP server via stdio
  - /exit       : Exit the interactive session
  - User prompts: Send to LLM which decides which tool to invoke

The LLM (Ollama qwen3:8b) receives user prompts and available tools,
and decides whether to invoke a tool. The client shows tool execution
results and [MCP Client -> MCP Server] communication logs.

Session logs are saved to the logs/ folder as JSON files.
Each file is named {session_id}.json and contains:
  timestamp, session_id, model, user_prompt, response, turn

Usage:
    PYTHONPATH=src uv run python3 -m app
    # or run directly with python3
    python3 src/app.py
    # or set OLLAMA_URL and OLLAMA_MODEL env vars
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
SERVER_SCRIPT = os.path.join(SRC_DIR, "mcp_server.py")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")

# Log directory for session logs (kept at project root)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# MCP client log file at project root
MCP_LOGS_FILE = os.path.join(PROJECT_ROOT, ".mcp_client_logs.txt")

# Session tracking
session_id: str = str(uuid.uuid4())

# Tool registry: name -> {description, inputSchema}
TOOLS: Dict[str, Dict[str, Any]] = {
    "echo": {
        "name": "echo",
        "description": "Echo the user message at the screen. Useful to check that the client is working.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to echo at the screen"
                }
            },
            "required": ["message"]
        }
    }
}

# Built-in commands of the app
BUILTIN_COMMANDS = {"/help", "/tools", "/register", "/exit"}


def format_json(obj) -> str:
    """Format a JSON object on a single line for log readability."""
    return json.dumps(obj, sort_keys=True)


def log_app(text: str) -> None:
    """Print an [APP] log line (visible in terminal)."""
    print(f"\033[1;36m[APP]\033[0m {text}")


def log_llm(text: str) -> None:
    """Print an [LLM] log line (LLM response)."""
    print(f"\033[1;33m[LLM]\033[0m {text}")


def log_mcp(text: str) -> None:
    """Print an [MCP CLIENT -> MCP SERVER] log line (communication)."""
    print(f"\033[1;32m[MCP CLIENT -> MCP SERVER]\033[0m {text}")


def list_tools() -> None:
    """List all registered tools (echo + any MCP server tools)."""
    log_app("Registered tools:")
    if not TOOLS:
        print("  (none)")
        return
    for name, info in sorted(TOOLS.items()):
        print(f"  - \033[1m{name}\033[0m: {info['description']}")


def show_help() -> None:
    """Show the application help menu."""
    print()
    log_app("=== lab01-mcp-fundamentals - MCP Client Help ===")
    print("  \033[1m/tools\033[0m    - list the existing tools (echo + any MCP server tools)")
    print("  \033[1m/help\033[0m     - show this help menu")
    print("  \033[1m/register\033[0m - register an MCP Server via stdin (adds its tools)")
    print("  \033[1m/exit\033[0m     - exit the interactive session")
    print()
    print("  Then type any user prompt, e.g.:")
    print("    echo Hola")
    print("    echo \"Hello world\"")
    print("    read_security_message")
    print("  The LLM will decide which tool to use based on the prompt and available tools.")
    print("  After registering the MCP server, its tool becomes available:")
    print("    read_security_message")
    print()
    print("  Tool communication is shown with [MCP Client -> MCP Server] prefix.")
    print()


def send_message(process: subprocess.Popen, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Send a JSON-RPC message through the pipe and return the response."""
    print(format_json(message), file=sys.stderr)
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()
    log_mcp(f"< to MCP SERVER > {format_json(message)}")

    if message.get("id") is None:
        return None  # Notification - no response expected

    response_line = process.stdout.readline()
    response = json.loads(response_line)
    print(format_json(response), file=sys.stderr)
    log_mcp(f"< from MCP SERVER > {format_json(response)}")
    return response


def register_mcp_server() -> None:
    """Register the MCP Server via stdin transport."""
    log_app("Registering MCP Server (stdio transport)...")
    if not os.path.exists(SERVER_SCRIPT):
        print(f"[ERROR] MCP Server script not found: {SERVER_SCRIPT}")
        return

    # Read the MCP server's stderr so we can show the communication.
    # The server writes its log lines to stderr, so we redirect stderr to a
    # pipe, read it line by line, and print it as [MCP CLIENT -> MCP SERVER]
    # communication. stdout is used for the JSON-RPC protocol by the server.
    process = subprocess.Popen(
        ["python3", SERVER_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    log_app("MCP Server started as subprocess (stdio).")
    time.sleep(0.3)

    # 1. initialize handshake
    log_app("Step 1/3: send initialize request to MCP Server...")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "lab01-mcp-client", "version": "1.0.0"}
        }
    }
    send_message(process, init_request)

    # 2. initialized notification
    log_app("Step 2/3: send initialized notification...")
    send_message(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})

    # 3. list tools
    log_app("Step 3/3: list tools of MCP Server...")
    tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    tools_response = send_message(process, tools_request)

    new_tools = 0
    if tools_response and "result" in tools_response and "tools" in tools_response["result"]:
        for tool_def in tools_response["result"]["tools"]:
            tool_name = tool_def.get("name")
            if tool_name:
                TOOLS[tool_name] = {
                    "name": tool_name,
                    "description": tool_def.get("description", "No description available."),
                    "inputSchema": tool_def.get("inputSchema", {"type": "object", "properties": {}})
                }
                new_tools += 1
                log_app(f"Tool registered: \033[1m{tool_name}\033[0m")

    log_app(f"MCP Server registered. New tools: {new_tools}. "
            f"Total tools now: {len(TOOLS)}")

    process.terminate()
    process.wait(timeout=5)

    # Save the captured communication log for later review
    save_mcp_log(process)


def save_mcp_log(process: subprocess.Popen) -> None:
    """Save the MCP server stderr (communication log) to a file."""
    stderr_lines = []
    try:
        for line in process.stderr:
            line = line.rstrip("\n")
            if line:
                stderr_lines.append(line)
    except (OSError, ValueError):
        pass

    if stderr_lines:
        with open(MCP_LOGS_FILE, "w") as f:
            f.write("\n".join(stderr_lines) + "\n")


def call_echo_tool(arguments: Dict[str, Any]) -> str:
    """The built-in echo tool: echo the message at the screen."""
    message = arguments.get("message", "")
    return f"Echo: {message}"


TOOL_HANDLERS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    "echo": call_echo_tool,
}


def call_mcp_server_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Call a tool on the MCP Server via stdin/stdout (stdio transport)."""
    if not os.path.exists(SERVER_SCRIPT):
        raise ValueError(f"MCP Server script not found: {SERVER_SCRIPT}")

    process = subprocess.Popen(
        ["python3", SERVER_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        # 1. initialize handshake
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "lab01-mcp-client", "version": "1.0.0"}
            }
        }
        init_response = send_message(process, init_request)
        if not init_response or "result" not in init_response:
            raise ValueError("MCP Server initialize failed")

        # 2. initialized notification
        send_message(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 3. call the tool
        call_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        call_response = send_message(process, call_request)
        if not call_response:
            raise ValueError("No response from MCP Server")

        if "error" in call_response:
            error_msg = call_response["error"].get("message", "Unknown error")
            raise ValueError(f"MCP Server error: {error_msg}")

        if "result" not in call_response:
            raise ValueError("No result from MCP Server")

        # Extract the text content
        result = call_response["result"]
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                first = content[0]
                if isinstance(first, dict) and first.get("type") == "text":
                    return first.get("text", "")

        # Fallback: return JSON string of result
        return json.dumps(result)

    finally:
        process.terminate()
        process.wait(timeout=5)


def run_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Run a registered tool with the given arguments."""
    # First check built-in handlers
    handler = TOOL_HANDLERS.get(tool_name)
    if handler:
        return handler(arguments)

    # Then check if it's an MCP server tool we know about
    if tool_name in TOOLS:
        return call_mcp_server_tool(tool_name, arguments)

    raise ValueError(f"Tool '{tool_name}' is not available. "
                     f"Use /register to load an MCP server with this tool.")


def tools_to_ollama_format() -> List[Dict[str, Any]]:
    """Convert MCP tool registry to Ollama function definitions."""
    ollama_tools = []
    for name, info in sorted(TOOLS.items()):
        func = {
            "name": name,
            "description": info.get("description", ""),
            "parameters": info.get("inputSchema", {"type": "object", "properties": {}})
        }
        ollama_tools.append({"type": "function", "function": func})
    return ollama_tools


def ollama_chat(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Call Ollama chat API with tools."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "tools": tools,
        "stream": False
    }
    url = f"{OLLAMA_URL}/api/chat"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def process_prompt(prompt: str, turn: int = 0) -> None:
    """Send user prompt to LLM, handle tool calls."""
    messages = [{"role": "user", "content": prompt}]
    ollama_tools = tools_to_ollama_format()

    try:
        response = ollama_chat(messages, ollama_tools)
        message = response.get("message", {})

        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")

        if tool_calls:
            log_llm("LLM decided to invoke tool(s).")
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name")
                arguments = func.get("arguments", {})
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)

                try:
                    result = run_tool(tool_name, arguments)
                    log_app(f"Tool [{tool_name}] executed. Result:")
                    print(f"    {result}")
                    response_str = f"Tool [{tool_name}] executed: {result}"
                    log_interaction(turn, prompt, response_str)
                except ValueError as e:
                    print(f"[ERROR] {e}")
                    log_interaction(turn, prompt, f"Error: {e}")
        elif content:
            log_llm("LLM response (no tool calls):")
            print(f"\033[1;33m{content}\033[0m")
            log_interaction(turn, prompt, content)
        else:
            log_llm("LLM returned empty response.")
            log_interaction(turn, prompt, "")

    except urllib.error.URLError as e:
        print(f"[ERROR] Failed to connect to Ollama at {OLLAMA_URL}: {e}")
        print("[APP] Make sure Ollama is running and accessible.")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

    except urllib.error.URLError as e:
        print(f"[ERROR] Failed to connect to Ollama at {OLLAMA_URL}: {e}")
        print("[APP] Make sure Ollama is running and accessible.")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")


def log_interaction(turn: int, user_prompt: str, response: str) -> None:
    """Save interaction to a JSON log file named session_id.json."""
    log_entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "model": OLLAMA_MODEL,
        "user_prompt": user_prompt,
        "response": response,
        "turn": turn,
    }

    # Write to a file named session_id.json in the logs folder
    log_path = os.path.join(LOG_DIR, f"{session_id}.json")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


def run_interactive_loop() -> None:
    """Run the interactive menu loop."""
    log_app("=== lab01-mcp-fundamentals MCP Client ===")
    print("  Commands: /help, /tools, /register, /exit")
    print("  Or type a user prompt, e.g.: echo Hola")
    print("  Press Ctrl+C to quit")
    print()

    turn = 0

    while True:
        try:
            prompt = input("> ").strip()
        except EOFError:
            # Handle Ctrl+D
            break

        if not prompt:
            continue

        if prompt in BUILTIN_COMMANDS:
            if prompt == "/help":
                show_help()
            elif prompt == "/tools":
                list_tools()
            elif prompt == "/register":
                register_mcp_server()
            elif prompt == "/exit":
                log_app("Goodbye!")
                break
        else:
            turn += 1
            process_prompt(prompt, turn)
        print()


if __name__ == "__main__":
    try:
        run_interactive_loop()
    except KeyboardInterrupt:
        print("\n[APP] Goodbye!")
        sys.exit(0)