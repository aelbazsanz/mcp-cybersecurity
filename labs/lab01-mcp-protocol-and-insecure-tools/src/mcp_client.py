"""MCP Client module — speaks the MCP protocol over stdio with a server.

This is the "client side" of the MCP connection. The app (Host) creates an
MCPClient instance, calls connect() to start the server and run the handshake,
then calls list_tools() / call_tool() / etc. The client handles the JSON-RPC
wire protocol so the app doesn't have to.

Flow annotations are printed on every message so you can see exactly who
talks to whom: [APP → MCP Client], [MCP Client → MCP Server], etc.
"""
import json
import subprocess
import sys
from typing import Any


class MCPClient:
    """Manages a connection to one MCP server over stdio."""

    def __init__(self, server_path: str, label: str = "mcp"):
        self._server_path = server_path
        self._label = label
        self._proc: subprocess.Popen | None = None
        self._tools: list[dict] = []
        self._resources: list[dict] = []
        self._next_message_id = 0

    # ── Public API (called by the app / Host) ──────────────────────

    def connect(self) -> None:
        """Start the server process and run the MCP initialize handshake."""
        print(f"[APP → MCP Client] Connect to {self._label} server")
        self._proc = subprocess.Popen(
            [sys.executable, self._server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._handshake()
        print(f"[MCP Client ← MCP Server] Ready. Tools: {[t['name'] for t in self._tools]}")

    def list_tools(self) -> list[dict]:
        """Return the tools the server announced during handshake."""
        return self._tools

    def list_resources(self) -> list[dict]:
        """Return the resources the server announced during handshake."""
        return self._resources

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool on the server and return the result text."""
        print(f"[APP → MCP Client] call_tool({name}, {arguments})")
        reply = self._send_request("tools/call", {"name": name, "arguments": arguments})
        content = reply.get("result", {}).get("content", [])
        text = "\n".join(c.get("text", "") for c in content)
        print(f"[MCP Client ← MCP Server] result: {text!r}")
        return text

    def read_resource(self, uri: str) -> str:
        """Read a resource from the server."""
        print(f"[APP → MCP Client] read_resource({uri})")
        reply = self._send_request("resources/read", {"uri": uri})
        # Resources use "contents" (array of {uri, mimeType, text})
        contents = reply.get("result", {}).get("contents", [])
        text = "\n".join(c.get("text", "") for c in contents)
        print(f"[MCP Client ← MCP Server] result: {text!r}")
        return text

    def close(self) -> None:
        """Shutdown the server process."""
        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=5)
            print(f"[APP → MCP Client] Disconnected from {self._label} server")

    # ── Internal: MCP JSON-RPC protocol ────────────────────────────

    def _handshake(self) -> None:
        """Run the MCP initialize handshake: initialize → initialized → tools/list → resources/list."""
        # 1. Send initialize
        print(f"[MCP Client → MCP Server] initialize")
        self._send({
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "lab01-app", "version": "0.1.0"},
            },
        })
        reply = self._recv()
        proto = reply.get("result", {}).get("protocolVersion", "unknown")
        print(f"[MCP Server → MCP Client] initialize reply: protocolVersion={proto}")

        # 2. Send initialized notification (no id, no reply expected)
        print(f"[MCP Client → MCP Server] notifications/initialized")
        self._notify("notifications/initialized")

        # 3. List tools
        print(f"[MCP Client → MCP Server] tools/list")
        tools_reply = self._send_request("tools/list", {})
        self._tools = tools_reply.get("result", {}).get("tools", [])
        print(f"[MCP Server → MCP Client] tools: {[t['name'] for t in self._tools]}")

        # 4. List resources
        print(f"[MCP Client → MCP Server] resources/list")
        res_reply = self._send_request("resources/list", {})
        self._resources = res_reply.get("result", {}).get("resources", [])
        print(f"[MCP Server → MCP Client] resources: {[r.get('name', r.get('uri')) for r in self._resources]}")

    def _send_request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and wait for the reply with matching id."""
        msg_id = self._next_id()
        wire = json.dumps({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}, ensure_ascii=False)[:200]
        print(f"[MCP Client → MCP Server] {method}: {wire}")
        self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()
        # Wait for reply with matching id (skip any interleaved notifications)
        while True:
            msg = self._recv()
            if msg.get("id") == msg_id:
                return msg
            # If it's a notification (no id), loop continues

    def _notify(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no id, no reply expected)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._send(msg)

    def _send(self, msg: dict) -> None:
        """Serialize and send a JSON-RPC message to the server's stdin."""
        line = json.dumps(msg, ensure_ascii=False)
        # Print wire message (truncated for readability)
        wire = line[:200] + ("..." if len(line) > 200 else "")
        print(f"  → {wire}")
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()

    def _recv(self) -> dict:
        """Read one line from server stdout and parse as JSON-RPC."""
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("Server closed the connection")
        msg = json.loads(line)
        wire = line[:200] + ("..." if len(line) > 200 else "")
        print(f"  ← {wire}")
        return msg

    def _next_id(self) -> int:
        self._next_message_id += 1
        return self._next_message_id