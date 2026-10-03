# Lab01 — MCP protocol anatomy and insecure tools

**No LLM, no agents, no network.** A hand-written JSON-RPC client talks to an MCP
server over stdio. First you see the protocol "raw"; then you exploit two classic
server-side flaws and fix them.

## Objectives

1. Understand the MCP lifecycle: `initialize` → `notifications/initialized` → `tools/list` → `tools/call`.
2. See what a server publishes in `tools/list` (names, descriptions, schemas): this is what an LLM will read later on.
3. Exploit **path traversal** (CWE-22) and **command injection** (CWE-78) in MCP tools.
4. Apply the fix and verify that the attack is blocked.

Key idea: **a tool's arguments are chosen by the model, or by whoever manipulates it**.
The MCP server must treat them as untrusted input, exactly like a web endpoint.
(In the OWASP Top 10 for LLM Applications this touches LLM05 —improper output handling— and LLM06 —excessive agency.)

## Contents

| File | Purpose |
|---|---|
| `src/server.py` | **Vulnerable** notes server: `list_notes`, `read_note`, `search_notes` |
| `src/server_secure.py` | Same server, **fixed** |
| `src/client.py` | Minimal JSON-RPC client (no SDK) with `handshake` and `exploit` scenarios |
| `data/notes/` | Legitimate notes |
| `data/secret.txt` | **Fictitious** secret (`FLAG{...}` canary) located outside the notes directory |
| `logs/` | `.jsonl` trace of every run |

## Running with Docker (recommended)

The vulnerable server executes shell commands, so it runs in a container with no network,
no capabilities and a read-only filesystem.

```bash
cp .env.example .env              # MCP_SERVER=vulnerable | secure
docker compose build
docker compose run --rm lab01                        # handshake (default)
docker compose run --rm lab01 --scenario exploit
```

Logs are written to `./logs/` as uid 1000. If your user is not 1000, adjust `user:` in the compose file.

## Running locally with uv

```bash
uv sync
uv run python src/client.py --scenario handshake
MCP_SERVER=vulnerable uv run python src/client.py --scenario exploit
```

Note: when run locally, the vulnerable server runs on your machine. The payloads only read the fictitious file, but prefer Docker.

## Exercises

1. **Handshake.** Run the `handshake` scenario and answer: which capabilities does the server announce? Why does `notifications/initialized` carry no `id`? Which field of `tools/list` would an LLM read to decide which tool to use?
2. **Path traversal.** Run `exploit` against `MCP_SERVER=vulnerable`. Which argument lets you escape `data/notes/`? Also try an absolute path (`/etc/passwd`) by editing the payload.
3. **Command injection.** Look at how the `grep` command line is built in `server.py`. Why does the payload need `;` and `#`?
4. **Fix.** Switch to `MCP_SERVER=secure` and repeat. Read `server_secure.py`: what do `resolve()` and `is_relative_to()` do? Why is removing the shell better than filtering characters?
5. **Log analysis with jq.**
   ```bash
   jq -c 'select(.direction=="client->server") | .message.method' logs/*.jsonl
   jq -c 'select(.event=="verdict") | {server, attack, leaked}' logs/*.jsonl
   ```

## Expected results

| Attack | `vulnerable` | `secure` |
|---|---|---|
| Path traversal (`../secret.txt`) | EXPLOITED | BLOCKED |
| Command injection (`; cat ...`) | EXPLOITED | BLOCKED |

## Mitigations (summary)

- Resolve paths to their canonical form and check that they stay inside the allowed directory.
- Never pass external input to a shell; use native APIs, or `subprocess` with an argument list and `shell=False`.
- Least privilege: container without network, unprivileged user, read-only filesystem.
- With stdio, never write to stdout outside the protocol (it breaks the session).

## Next

Lab02: HTTP transport, authentication and network exposure.
