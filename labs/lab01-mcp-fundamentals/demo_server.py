#!/usr/bin/env python3
"""
Simple MCP Server Demo

This script demonstrates an MCP Server that:
1. Receives JSON-RPC 2.0 messages from stdin (from the MCP Client)
2. Processes them according to the MCP protocol
3. Simulates a data source (in-memory "database")
4. Sends JSON-RPC responses back to stdout (to the MCP Client)
"""

import json
import sys
from typing import Dict, Any

# Simulated in-memory "database"
DATABASE = {
    "users": [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "user"},
        {"id": 3, "name": "Charlie", "role": "user"}
    ],
    "products": [
        {"id": 101, "name": "Laptop", "price": 999.99},
        {"id": 102, "name": "Mouse", "price": 25.50},
        {"id": 103, "name": "Keyboard", "price": 75.00}
    ]
}

def format_json(obj) -> str:
    """Format a JSON object on a single line for log readability."""
    return json.dumps(obj, sort_keys=True)

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
                        "serverInfo": {"name": "demo-mcp-server", "version": "1.0.0"}
                    }
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [{
                            "name": "query_database",
                            "description": "Query the simulated database",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "table": {
                                        "type": "string",
                                        "enum": ["users", "products"],
                                        "description": "Database table to query"
                                    }
                                },
                                "required": ["table"]
                            }
                        }]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name == "query_database":
                    table = arguments.get("table")
                    if table in DATABASE:
                        result_text = json.dumps(DATABASE[table], indent=2)
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [{"type": "text", "text": result_text}]
                            }
                        }
                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32602,
                                "message": f"Invalid table: {table}"
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