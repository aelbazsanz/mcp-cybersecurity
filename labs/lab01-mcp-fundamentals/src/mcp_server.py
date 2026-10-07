#!/usr/bin/env python3
"""
MCP Server for lab01-mcp-fundamentals

This script demonstrates an MCP Server that:
1. Receives JSON-RPC 2.0 messages from stdin (from the MCP Client)
2. Processes them according to the MCP protocol
3. Implements a read_security_message tool that reads from data/security.txt
4. Sends JSON-RPC responses back to stdout (to the MCP Client)

Usage:
    PYTHONPATH=src uv run python3 -m mcp_server
    # or
    python3 src/mcp_server.py
"""

import json
import sys
import os
from typing import Dict, Any


def format_json(obj) -> str:
    """Format a JSON object on a single line for log readability."""
    return json.dumps(obj, sort_keys=True)


def read_security_message() -> str:
    """Read the security message from data/security.txt"""
    try:
        # data/ lives at the project root, one level above this script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        security_path = os.path.join(project_root, "data", "security.txt")
        with open(security_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Error: security.txt not found"
    except Exception as e:
        return f"Error reading security message: {str(e)}"


def main():
    """Main server loop - reads JSON-RPC from stdin, writes responses to stdout."""

    # Read line by line from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)

            # Show what we received (from the MCP Client)
            print(f"[MCP SERVER] < from MCP CLIENT > {format_json(request)}", file=sys.stderr)

            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # Handle different methods
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2026-07-28",
                        "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                        "serverInfo": {"name": "mcp-security-server", "version": "1.0.0"}
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [{
                            "name": "read_security_message",
                            "description": "Read the security message from data/security.txt",
                            "inputSchema": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False
                            }
                        }]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name == "read_security_message":
                    # No arguments needed for this tool
                    security_content = read_security_message()
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": security_content}]
                        }
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {tool_name}"
                        }
                    }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            # Show what we are sending (to the MCP Client)
            # Only for requests with an id (notifications have no response)
            if "id" in request and request["id"] is not None:
                print(f"[MCP SERVER] < to MCP CLIENT > {format_json(response)}", file=sys.stderr)
                print(json.dumps(response))
                sys.stdout.flush()

        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            print(f"[MCP SERVER] < to MCP CLIENT > {format_json(error_response)}", file=sys.stderr)
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)