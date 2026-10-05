#!/usr/bin/env python3
"""
MCP Client for lab01-mcp-fundamentals

This script demonstrates an MCP Client that:
1. Provides an interactive menu: /tools, /help, /register
2. Has a built-in 'echo' tool that echoes the user's message
3. Registers an MCP Server via stdin transport when /register is used
4. Shows the JSON-RPC communication with [MCP Client -> MCP Server] style logs
5. Simulates the LLM step: the LLM sees the available tools and instructs
   which tool to invoke for the user prompt

Usage:
    python3 demo_client.py

When the menu shows, you can type a user prompt (e.g., "echo Hola").
The app simulates the LLM response (instructing to use a tool) and then
runs the tool, printing the result.
"""

import json
import os
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional, Callable

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(APP_DIR, "demo_server.py")

# In-memory tool registry: name -> {description, input_schema}
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
BUILTINS = {"/help", "/tools", "/register"}

# Where MCP server logs are written (captured stderr)
MCP_LOGS_FILE = os.path.join(APP_DIR, ".mcp_client_logs.txt")


def format_json(obj) -> str:
    """Format a JSON object on a single line for log readability."""
    return json.dumps(obj, sort_keys=True)


def log_app(text: str) -> None:
    """Print an [APP] log line (visible in terminal)."""
    print(f"\033[1;36m[APP]\033[0m {text}")


def log_llm(text: str) -> None:
    """Print an [LLM] log line (simulated LLM response)."""
    print(f"\033[1;33m[LLM]\033[0m {text}")


def log_mcp(text: str) -> None:
    """Print an [MCP CLIENT] log line (MCP client -> server communication)."""
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
    print()
    print("  Then type any user prompt, e.g.:")
    print("    echo Hola")
    print("    echo \"Hello world\"")
    print("  The LLM will decide which tool to use and the tool will run.")
    print("  After registering the MCP server, its tool becomes available:")
    print("    read_security_message")
    print("  Press Ctrl+C to quit.")
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


def execute_user_prompt(prompt: str) -> None:
    """
    Simulate the LLM step for a user prompt.

    The LLM 'sees' the registered tools and responds with an instruction
    on which tool to invoke. Then the app runs the tool and prints the result.
    """
    prompt = prompt.strip()
    if not prompt:
        return

    log_app(f"User prompt: \033[1m{prompt}\033[0m")

    # Decide which tool the LLM would pick (simulated).
    # This is the LLM step: the LLM observes the available tools and decides.
    # Preference order:
    #   1. If the prompt mentions a registered MCP tool by name, use it.
    #   2. If the prompt starts with "echo ", use the echo tool.
    #   3. Fallback to echo for simple messages (built-in).
    chosen_tool: Optional[str] = None
    tool_args: Dict[str, Any] = {}

    for tool_name in sorted(TOOLS):
        if tool_name == "read_security_message" and "security" in prompt.lower():
            chosen_tool = tool_name
            break

    if not chosen_tool and "echo" in TOOLS:
        if prompt.lower().startswith("echo "):
            chosen_tool = "echo"
            tool_args["message"] = prompt[5:].strip()
        elif len(TOOLS) == 1:
            # Only echo is available — treat any message as an echo.
            chosen_tool = "echo"
            tool_args["message"] = prompt

    if chosen_tool:
        log_llm(f"I will use the \033[1m{chosen_tool}\033[0m tool to handle your request.")
        try:
            result = run_tool(chosen_tool, tool_args)
            log_app(f"Tool [{chosen_tool}] executed. Result:")
            print(f"\033[1;36m    {result}\033[0m")
        except ValueError as e:
            print(f"[ERROR] {e}")
            print("[APP] Use /register to load an MCP server with more tools.")
    else:
        # Fallback: no tool was picked.
        if len(TOOLS) == 1 and "echo" in TOOLS:
            # Only echo — echo the message as a last resort.
            log_llm("I will use the \033[1mecho\033[0m tool to echo your message at the screen.")
            result = run_tool("echo", {"message": prompt})
            log_app(f"Tool [echo] executed. Result:")
            print(f"\033[1;36m    {result}\033[0m")
        else:
            log_llm("I don't see a matching tool for your request.")
            print(f"[APP] Available tools: {', '.join(sorted(TOOLS.keys()))}")


def run_interactive_loop() -> None:
    """Run the interactive menu loop."""
    log_app("=== lab01-mcp-fundamentals MCP Client ===")
    print("  Commands: /help, /tools, /register")
    print("  Or type a user prompt, e.g.: echo Hola")
    print("  Press Ctrl+C to quit")
    print()

    while True:
        prompt = input("> ").strip()
        if not prompt:
            continue

        if prompt in BUILTINS:
            if prompt == "/help":
                show_help()
            elif prompt == "/tools":
                list_tools()
            elif prompt == "/register":
                register_mcp_server()
        else:
            execute_user_prompt(prompt)
        print()


if __name__ == "__main__":
    try:
        run_interactive_loop()
    except KeyboardInterrupt:
        print("\n[APP] Goodbye!")
        sys.exit(0)
