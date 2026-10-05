"""Minimal MCP client for lab01, with NO SDK and NO LLM.

Speaks JSON-RPC 2.0 directly to the server over stdio (one JSON message per
line) so you can see exactly what travels over the wire.

Scenarios:
  handshake  Lifecycle: initialize -> initialized -> tools/list -> tools/call -> resources/list -> resources/read
  explore    Inspect what the server announces (what the LLM "sees")
  call       Demonstrate a legitimate tool call
  interactive REPL to manually explore the protocol

Target server (config): MCP_SERVER environment variable = vulnerable | secure
  .env is the source of truth; the default below is only a safety net for
  running outside Docker.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = LAB_DIR / "logs"
SERVERS = {
    "vulnerable": "src/server_vulnerable.py",
    "secure": "src/server_secure.py",
}
DEFAULT_SERVER = "secure"  # start with secure to learn the protocol first
CANARY = "FLAG{mcp-lab01-fictitious-secret}"
PROTOCOL_VERSION = "2025-06-18"

# Terminal color codes (ANSI); used when stdout is a TTY.
_COLOR = {
    "green": "\033[32m",
    "red": "\033[31m",
    "reset": "\033[0m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
}

try:
    _TTY = sys.stdout.isatty()
except Exception:
    _TTY = False

if _TTY:
    GREEN = _COLOR["green"]
    RED = _COLOR["red"]
    YELLOW = _COLOR["yellow"]
    CYAN = _COLOR["cyan"]
    RESET = _COLOR["reset"]
else:
    GREEN = RED = YELLOW = CYAN = RESET = ""


class Wire:
    """Sends and receives JSON-RPC messages, prints them and logs them to .jsonl."""

    def __init__(self, proc: subprocess.Popen, log_path: Path):
        self.proc = proc
        self.log = log_path.open("a", encoding="utf-8")
        self._next_id = 0

    def _record(self, direction: str, message: dict) -> None:
        arrow = "-->" if direction == "client->server" else "<--"
        print(f"\n{arrow} {direction}")
        print(json.dumps(message, indent=2, ensure_ascii=False))
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "direction": direction,
            "message": message,
        }
        self.log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.log.flush()

    def event(self, name: str, **data) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": name, **data}
        self.log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.log.flush()

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        msg = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        while True:  # skip interleaved notifications until the reply with our id arrives
            reply = self._recv()
            if reply.get("id") == self._next_id:
                return reply

    def _send(self, msg: dict) -> None:
        self._record("client->server", msg)
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _recv(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(
                "The server closed the connection (use --server-stderr to see its error)"
            )
        msg = json.loads(line)
        self._record("server->client", msg)
        return msg

    def close(self) -> None:
        self.log.close()


def result_text(reply: dict) -> tuple[bool, str]:
    """Return (is_error, text) for a tools/call reply."""
    if "error" in reply:  # JSON-RPC protocol-level error
        return True, json.dumps(reply["error"], ensure_ascii=False)
    result = reply["result"]
    text = "\n".join(c.get("text", "") for c in result.get("content", []))
    return bool(result.get("isError")), text


def initialize(wire: Wire) -> None:
    wire.request(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "lab01-raw-client", "version": "0.1.0"},
        },
    )


def _fmt_status(text: str, status: str = "info") -> str:
    """Return text wrapped with ANSI color codes when running in a TTY."""
    if not _TTY:
        return text
    color = {
        "info": YELLOW,
        "success": GREEN,
        "warning": RED,
        "highlight": CYAN,
    }.get(status, YELLOW)
    return f"{color}{text}{RESET}"


def handshake(wire: Wire) -> None:
    """Run the full lifecycle and explain each step."""
    print("\n=== 1. initialize: client and server negotiate version and capabilities ===")
    initialize(wire)

    print("\n=== 2. notifications/initialized: the client confirms (no reply, it carries no id) ===")
    wire.notify("notifications/initialized")

    print("\n=== 3. tools/list: the server describes its tools (this is what an LLM reads) ===")
    tools_reply = wire.request("tools/list")
    print(_fmt_status("Tools announced by server:", "highlight"))
    for tool in tools_reply["result"]["tools"]:
        print(f"  • {tool['name']}: {tool.get('description', 'No description')}")

    print("\n=== 4. resources/list: the server describes its resources ===")
    resources_reply = wire.request("resources/list")
    print(_fmt_status("Resources announced by server:", "highlight"))
    for resource in resources_reply["result"]["resources"]:
        print(f"  • {resource.get('name', 'Unnamed')}: {resource.get('description', 'No description')}")

    print("\n=== 5. tools/call: legitimate use of a tool ===")
    wire.request("tools/call", {"name": "get_user_name", "arguments": {}})
    print(_fmt_status("Called get_user_name() — see response above", "success"))

    print("\n=== 6. resources/read: reading a resource ===")
    wire.request(
        "resources/read",
        {"uri": "resource://notes/welcome.md"},
    )
    print(_fmt_status("Read welcome.md — see response above", "success"))


def explore(wire: Wire) -> None:
    """Inspect what the server announces — simulating what an LLM would see."""
    print("\n=== EXPLORING SERVER CAPABILITIES (what the LLM 'sees') ===")

    # Get tools
    tools_reply = wire.request("tools/list")
    print(f"\n{_fmt_status('Available tools:', 'highlight')}")
    for tool in tools_reply["result"]["tools"]:
        print(f"  {_fmt_status(tool['name'], 'cyan')}: {tool.get('description', 'No description')}")

    # Get resources
    resources_reply = wire.request("resources/list")
    print(f"\n{_fmt_status('Available resources:', 'highlight')}")
    for resource in resources_reply["result"]["resources"]:
        print(f"  {_fmt_status(resource.get('name', 'Unnamed'), 'cyan')}: {resource.get('description', 'No description')}")

    print(
        f"\n{_fmt_status('Note: An LLM uses this information to decide which tool/resource to use.', 'info')}"
    )


def call(wire: Wire) -> None:
    """Demonstrate a legitimate tool call and resource read."""
    print("\n=== DEMONSTRATING TOOL CALLS AND RESOURCE READS ===")

    # Call get_user_name
    print(f"\n{_fmt_status('Calling get_user_name()...', 'info')}")
    reply = wire.request("tools/call", {"name": "get_user_name", "arguments": {}})
    _is_error, text = result_text(reply)
    print(f"{_fmt_status('Result:', 'success')} {text.strip()}")

    # Read a resource
    print(f"\n{_fmt_status('Reading resource://notes/welcome.md...', 'info')}")
    reply = wire.request(
        "resources/read", {"uri": "resource://notes/welcome.md"}
    )
    _is_error, text = result_text(reply)
    print(f"{_fmt_status('Resource contents:', 'success')}")
    print(text.rstrip())


def run_scenario_interactive(args, proc, wire) -> None:
    """Interactive REPL: user picks method + params, sees raw JSON-RPC round-trip."""
    print("\n=== INTERACTIVE MODE ===")
    print("Explore the protocol manually. Type:")
    print("  <method> <json-params>  (e.g. tools/list {})")
    print("  resources/read {\"uri\": \"resource://notes/welcome.md\"}")
    print("Blank line to exit. Ctrl-C to abort.")

    # Discover available methods once
    reply = wire.request("tools/list")
    tool_names = {t["name"] for t in reply["result"]["tools"]}
    reply = wire.request("resources/list")
    resource_names = {r.get("name", "") for r in reply["result"]["resources"]}

    while True:
        try:
            line = input("mcp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        parts = line.split(maxsplit=1)
        method = parts[0]
        if method not in {"tools/list", "resources/list", "tools/call", "resources/read"} and not (
            method.startswith("tools/call") or method.startswith("resources/read")
        ):
            print(
                f"Unknown method: {method}. Try: tools/list, resources/list, tools/call, resources/read"
            )
            continue
        args_json = parts[1] if len(parts) > 1 else "{}"
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            continue
        reply = wire.request(method, args)
        _is_error, text = result_text(reply)
        print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--scenario",
        choices=["handshake", "explore", "call", "interactive"],
        default="handshake",
    )
    parser.add_argument("--server-stderr", action="store_true", help="show the server's stderr")
    parser.add_argument(
        "--show-authority",
        action="store_true",
        help="after explore/call, show what the server is actually allowed to do",
    )
    args = parser.parse_args()

    server_name = os.environ.get("MCP_SERVER", DEFAULT_SERVER)
    if server_name not in SERVERS:
        print(f"MCP_SERVER must be one of {list(SERVERS)}, not '{server_name}'", file=sys.stderr)
        return 2

    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"lab01-{args.scenario}-{server_name}-{stamp}.jsonl"

    print(f"Server: {server_name} ({SERVERS[server_name]}) | scenario: {args.scenario}")
    proc = subprocess.Popen(
        [sys.executable, str(LAB_DIR / SERVERS[server_name])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None if args.server_stderr else subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    wire = Wire(proc, log_path)
    try:
        if args.scenario == "handshake":
            handshake(wire)
        elif args.scenario == "explore":
            explore(wire)
            if args.show_authority:
                print(
                    f"\n{_fmt_status('Authority note:', 'highlight')} The vulnerable server's tool descriptions"
                )
                print(
                    f"contain hidden instructions that could influence an LLM's behaviour."
                )
        elif args.scenario == "call":
            call(wire)
        elif args.scenario == "interactive":
            run_scenario_interactive(args, proc, wire)
    finally:
        wire.close()
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
    print(f"\n{_fmt_status('JSONL log:', 'info')} {log_path.relative_to(LAB_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())