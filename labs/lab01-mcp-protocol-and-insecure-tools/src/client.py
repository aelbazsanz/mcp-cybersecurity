"""Minimal MCP client for lab01, with NO SDK and NO LLM.

Speaks JSON-RPC 2.0 directly to the server over stdio (one JSON message per
line) so you can see exactly what travels over the wire.

Scenarios:
  handshake  Lifecycle: initialize -> initialized -> tools/list -> tools/call
  exploit    Sends path traversal and command injection payloads

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
SERVERS = {"vulnerable": "src/server.py", "secure": "src/server_secure.py"}
DEFAULT_SERVER = "vulnerable"  # documented fallback: only used outside Docker
CANARY = "FLAG{mcp-lab01-fictitious-secret}"
PROTOCOL_VERSION = "2025-06-18"


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
            raise RuntimeError("The server closed the connection (use --server-stderr to see its error)")
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


def handshake(wire: Wire) -> None:
    print("\n=== 1. initialize: client and server negotiate version and capabilities ===")
    initialize(wire)
    print("\n=== 2. notifications/initialized: the client confirms (no reply, it carries no id) ===")
    wire.notify("notifications/initialized")
    print("\n=== 3. tools/list: the server describes its tools (this is what an LLM reads) ===")
    wire.request("tools/list")
    print("\n=== 4. tools/call: legitimate use of a tool ===")
    wire.request("tools/call", {"name": "list_notes", "arguments": {}})
    wire.request("tools/call", {"name": "read_note", "arguments": {"name": "welcome.md"}})


def exploit(wire: Wire, server_name: str) -> None:
    # The lifecycle is mandatory before calling any tool, but we don't print its explanation here.
    initialize(wire)
    wire.notify("notifications/initialized")

    secret_path = LAB_DIR / "data" / "secret.txt"
    attacks = [
        ("Path traversal (CWE-22)", "read_note", {"name": "../secret.txt"}),
        (
            "Command injection (CWE-78)",
            "search_notes",
            # '/dev/null' keeps grep from waiting on stdin; '#' comments out the rest of the line.
            {"keyword": f"zzz /dev/null; cat {secret_path} #"},
        ),
    ]
    verdicts = []
    for title, tool, args in attacks:
        print(f"\n=== ATTACK: {title} ===")
        reply = wire.request("tools/call", {"name": tool, "arguments": args})
        is_error, text = result_text(reply)
        leaked = CANARY in text
        verdict = "EXPLOITED" if leaked else "BLOCKED"
        wire.event("verdict", attack=title, tool=tool, arguments=args, server=server_name,
                   leaked=leaked, is_error=is_error)
        verdicts.append((title, verdict))
    print(f"\n=== SUMMARY (server: {server_name}) ===")
    for title, verdict in verdicts:
        print(f"  [{verdict}] {title}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=["handshake", "exploit"], default="handshake")
    parser.add_argument("--server-stderr", action="store_true", help="show the server's stderr")
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
        else:
            exploit(wire, server_name)
    finally:
        wire.close()
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
    print(f"\nJSONL log: {log_path.relative_to(LAB_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
