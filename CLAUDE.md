# CLAUDE.md — mcp-cybersecurity

## What this repository is

A series of self-contained cybersecurity labs built around the **Model Context Protocol**
(MCP). Each lab starts small — often no LLM, no network — and grows toward realistic
agent/LLM scenarios. After each `lab0X-*` comes a matching `lab0X-*-audit` that reviews
the lab's security posture against frameworks such as **OWASP Top 10 for LLM
Applications**, **OWASP GenAI**, and **MITRE ATLAS**, plus any applicable governance
rules.

Remote: https://github.com/aelbazsanz/mcp-cybersecurity.git

## Layout

```
infrastructure/            Shared Ollama container (see INFRASTRUCTURE.md)
  docker-compose.yml       mcp-ollama on the shared mcp-network, host port 11435
labs/
  lab01-mcp-protocol-and-insecure-tools/   Lifecycle + path traversal + command injection
  lab02-...                                (HTTP transport, auth, network exposure)
  labNN-...
  labNN-*-audit/           Security review of the matching lab
```

## Tooling

- **Python** >= 3.11, **uv** as the sole package manager (`pyproject.toml` at each lab root).
- **Docker Compose** for the isolated vulnerable-server runs.
- **Git**: branch from `main`, commit with `Co-Authored-By: Claude Code <noreply@anthropic.com>`,
  PR descriptions end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- **No framework** in the early labs (lab01 uses the raw `mcp` package only). The MCP SDK
  is a dependency, but the client speaks JSON-RPC directly so the wire is visible.

## Conventions

- **`MCP_SERVER`** env var selects `vulnerable` vs `secure`. The `.env` is the source of
  truth inside Docker; the client falls back to `vulnerable` only when running locally.
- With stdio transport, **stdout is the protocol channel**. No `print()` in servers;
  debug goes to stderr.
- All client interactions are traced to `logs/` as `.jsonl` with timestamp + direction +
  message, plus `event` rows for verdicts — designed for `jq`.
- Vulnerable servers that execute shell commands run in a container with `network_mode:
  none`, `read_only: true`, `cap_drop: ALL`, `security_opt: no-new-privileges:true`.
- Tool arguments are treated as **untrusted input** (the central lesson). Path inputs are
  resolved and checked with `is_relative_to`; shell calls use `shell=False` or native APIs.
- A fictitious `FLAG{...}` canary lives in `data/secret.txt`; success = canary leaked.

## Lab01 — Current scenarios

| Scenario | What it does |
|---|---|
| `handshake` | Lifecycle: `initialize` → `notifications/initialized` → `tools/list` → `tools/call` |
| `exploit` | Path traversal + command injection against `MCP_SERVER` |
| `interactive` | REPL: pick a tool, type arguments, watch the raw JSON-RPC round-trip |
| `compare` | Run the same attacks against both servers, side-by-side verdict table |

`--show-secret` prints the canary-leak summary after `exploit` or `compare`.

## Working here

### Running lab01
```
cd labs/lab01-mcp-protocol-and-insecure-tools
cp .env.example .env && docker compose build
docker compose run --rm lab01                          # handshake (default)
docker compose run --rm lab01 --scenario exploit
docker compose run --rm lab01 --scenario interactive
docker compose run --rm lab01 --scenario compare
```
Locally without Docker:
```
uv sync
uv run python src/client.py --scenario handshake
MCP_SERVER=secure uv run python src/client.py --scenario exploit
uv run python src/client.py --scenario compare
```

### Adding a lab
1. Create `labs/lab0N-<short-description>/`.
2. Add `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `src/{server,client}.py`,
  `data/`, `logs/` (gitignored), `.env.example`, `README.md`.
3. Register the lab in the top-level repo `README.md` lab index.
4. Update `infrastructure/INFRASTRUCTURE.md` when the lab needs Ollama (the note says
  "Labs 01-03 do not need Ollama"; update that line as labs cross that threshold).

### Before writing a lab audit (`lab0X-*-audit`)
- Wait until the corresponding lab is complete.
- Map each finding to an OWASP LLM / GenAI category or MITRE ATLAS technique.
- Reference the exact `logs/*.jsonl` trace and `jq` commands to reproduce.

## Security reminders for Claude
- Keep the vulnerable code **contained**: never run it on the host network or with
  elevated privileges. Prefer Docker.
- The canary file is fictitious; do not invent real secrets.
- When a request would expand scope beyond lab boundaries or bypass an audit gate
  (e.g., jumping to lab04 while lab02 is unfinished), use `AskUserQuestion` rather than
  proceeding.
