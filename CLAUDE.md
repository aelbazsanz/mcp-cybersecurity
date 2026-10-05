# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About this project

This repo is a collection of hands-on labs for learning MCP (Model Context Protocol) security, tool integration, and defensive security practices. Labs 01-03 run without an LLM; Ollama is used starting from lab04.

## Running the code

```bash
# Lab 01 - MCP fundamentals
cd labs/lab01-mcp-fundamentals
uv run python3 -m app       # interactive MCP client
python3 app.py              # equivalent without uv

uv run python3 -m mcp_server  # run the MCP server standalone (for debugging)
python3 mcp_server.py       # direct execution

# Ollama (labs 04+)
cd infrastructure
docker compose up -d
docker exec -it mcp-ollama ollama pull qwen3:8b
docker exec -it mcp-ollama ollama list
```

## Architecture

### lab01-mcp-fundamentals

Two Python modules implement the MCP client-server flow over JSON-RPC 2.0 (stdio transport):

- `app.py` — the interactive MCP client. It runs a menu (`/help`, `/tools`, `/register`, `/exit`) and sends user prompts to Ollama (`qwen3:8b` at `http://localhost:11434`) via `POST /api/chat`, with tool definitions built from the local tool registry (the built-in `echo` tool plus tools discovered from the MCP server). The LLM response may contain `tool_calls`; the client executes those — built-in handlers directly, or MCP server tools by restarting the server subprocess and sending `tools/call`. Tool execution results are displayed to the user.

- `mcp_server.py` — the MCP server. It reads JSON-RPC requests from stdin and writes responses to stdout, implementing `initialize`, `notifications/initialized`, `tools/list`, and `tools/call`. The `read_security_message` tool reads `data/security.txt`.

Interaction flow:

```
uv run python3 -m app  ──► Ollama (qwen3:8b) — sends prompt + tools, receives tool_calls or text
        │
        └─/register► mcp_server.py (subprocess, stdio JSON-RPC 2.0)
```

### Ollama infrastructure (`infrastructure/`)

`docker-compose.yml` defines the `mcp-ollama` container (service name `ollama`, host port 11434). Labs that need an LLM join the `mcp-network` as an external network and reach Ollama at `http://ollama:11434`. The Compose project name is pinned (`name: mcp-infra`) so a lab's `infrastructure` folder never shares a project with the shared one.

## Important conventions

- Session logs (`logs/`, `logs/{session_id}.json`) are git-ignored — never commit them.
- `data/security.txt` is explicitly tracked even though `data/` is ignored (`!data/security.txt` in `.gitignore`).
- Each lab is self-contained; use its own `README.md` for lab-specific commands and documentation.

## Key files

- `labs/lab01-mcp-fundamentals/app.py` — MCP client (main interactive entry point)
- `labs/lab01-mcp-fundamentals/mcp_server.py` — MCP server with `read_security_message`
- `labs/lab01-mcp-fundamentals/data/security.txt` — security message read by the server tool
- `infrastructure/docker-compose.yml`, `infrastructure/INFRASTRUCTURE.md` — Ollama setup for labs 04+