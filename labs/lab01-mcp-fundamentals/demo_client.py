#!/usr/bin/env python3
"""
Simple MCP Client Demo

This script demonstrates an MCP Client that:
1. Starts the MCP Server as a subprocess (stdio transport)
2. Discovers the server's capabilities via initialize
3. Lists available tools
4. Calls a tool to query the database
5. Receives and displays the result
"""

import json
import subprocess
import sys
import time
from typing import Dict, Any, Optional

def format_json(obj) -> str:
    """Format a JSON object on a single line for log readability."""
    return json.dumps(obj, sort_keys=True)

def send_request(process, request: Dict) -> Dict[str, Any]:
    """Send a JSON-RPC request and read the response."""
    print(f"[MCP CLIENT] < to MCP SERVER > {format_json(request)}", file=sys.stderr)
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    response_line = process.stdout.readline()
    response = json.loads(response_line)
    print(f"[MCP CLIENT] < from MCP SERVER > {format_json(response)}", file=sys.stderr)
    return response

def send_notification(process, notification: Dict):
    """Send a JSON-RPC notification (no response expected)."""
    print(f"[MCP CLIENT] < to MCP SERVER > {format_json(notification)}", file=sys.stderr)
    process.stdin.write(json.dumps(notification) + "\n")
    process.stdin.flush()

def main():
    """Run the full MCP demo flow."""

    # Step 1: Start the MCP Server
    print("[APP] Start: launching MCP Server...", file=sys.stderr)
    process = subprocess.Popen(
        ["python", "demo_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    print("[APP] MCP Server running", file=sys.stderr)
    time.sleep(0.3)

    # Step 2: Discovery - initialize handshake
    print("[APP] Step 1: Discover server (initialize)", file=sys.stderr)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "demo-mcp-client", "version": "1.0.0"}
        }
    }
    send_request(process, request)

    # Step 3: Send initialized notification
    print("[APP] Step 2: Send initialized notification", file=sys.stderr)

    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    send_notification(process, notification)

    # Step 4: List available tools
    print("[APP] Step 3: List available tools", file=sys.stderr)

    request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    send_request(process, request)

    # Step 5: Call a tool to query the database
    print("[APP] Step 4: Call tool (query_database)", file=sys.stderr)

    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "query_database", "arguments": {"table": "users"}}
    }
    response = send_request(process, request)

    # Show the actual data received
    if "result" in response:
        content = response.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            data_text = content[0].get("text", "")
            print("[APP] Data received:", file=sys.stderr)
            for line in data_text.strip().split("\n"):
                print(f"[APP]   {line}", file=sys.stderr)

    # Step 6: Cleanup
    print("[APP] Stop: terminating MCP Server...", file=sys.stderr)
    process.terminate()
    process.wait(timeout=5)

    print("[APP] Done!", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())