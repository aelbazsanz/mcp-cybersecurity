# MCP Cybersecurity Labs

A collection of hands-on labs for learning MCP (Model Context Protocol) security concepts, tool integration, and defensive security practices.

## Project Structure

```
mcp-cybersecurity/
├── README.md                     # This file
├── .gitignore                    # Git ignore rules for logs, caches, etc.
├── .claude/                      # Claude Code settings
│   └── settings.json
├── infrastructure/               # Shared Ollama infrastructure (for labs 04+)
│   ├── docker-compose.yml       # Ollama container definition
│   └── INFRASTRUCTURE.md        # How to start Ollama and connect from labs
├── labs/
│   ├── lab01-mcp-fundamentals/   # Lab 01: MCP protocol basics with real LLM
│   │   ├── src/
│   │   │   ├── app.py            # Interactive MCP Client with real LLM (Ollama)
│   │   │   ├── mcp_server.py     # MCP Server with read_security_message tool
│   │   │   └── __init__.py       # Makes src a package (empty)
│   │   ├── data/
│   │   │   └── security.txt      # Security message read by server tool
│   │   ├── logs/                # Session logs (auto-generated, not tracked)
│   │   ├── pyproject.toml       # uv project config
│   │   └── README.md            # Lab-specific documentation
│   ├── lab02-mcp-toolinjection/   # Lab 02: prompt injection via tool descriptions
│   │   ├── app.py                # Interactive MCP Client with poisoned tool
│   │   ├── mcp_server.py         # MCP Server with hidden behavior
│   │   ├── data/
│   │   │   ├── security.txt      # Security message (normal behavior)
│   │   │   └── secret.txt        # Secret file (leaked by injection)
│   │   ├── logs/                 # Session logs (auto-generated, not tracked)
│   │   ├── pyproject.toml        # uv project config
│   │   └── README.md             # Lab-specific documentation
│   ├── lab02-mcp-audit/          # Lab 02 audit: audit lab02-mcp-toolinjection
│   │   ├── audit.py              # Audit script (runs vulnerability demo + maps frameworks)
│   │   ├── audit_methodology.md  # Audit steps and methodology
│   │   ├── frameworks/           # Framework mapping documents
│   │   │   ├── owasp_llm_top10.md
│   │   │   └── mitre_atlas.md
│   │   ├── report_template.md    # Final vulnerability report template
│   │   ├── src/                  # Replicated vulnerable code
│   │   ├── evidence/             # Collected evidence from audit
│   │   ├── pyproject.toml        # uv project config
│   │   └── README.md             # Lab-specific documentation
│   └── ... (future labs)
│       ├── lab03-mcp-resources/
│       └── lab04-ollama-integration/
```

## Quick Start: Lab 01 - MCP Fundamentals

```bash
cd labs/lab01-mcp-fundamentals

# Run the interactive MCP Client
PYTHONPATH=src uv run python3 -m app

# Alternative: run directly with python3
python3 src/app.py
```

**Lab 01 demonstrates**:
- MCP protocol handshake (`initialize` / `notifications/initialized` / `tools/list`)
- Tool registration via stdio transport (JSON-RPC 2.0)
- Real LLM integration with Ollama (qwen3:8b)
- LLM-decided tool invocation based on user prompts
- Communication visualization with `[MCP Client -> MCP Server]` logs
- Session logging to JSON files

**Start with**: `cd labs/lab01-mcp-fundamentals/README.md`

## Quick Start: Lab 02 - Tool Description Injection

```bash
cd labs/lab02-mcp-toolinjection

# Run the interactive MCP Client (same as lab01)
uv run python3 -m app
```

**Lab 02 demonstrates**:
- Prompt injection via malicious tool descriptions
- How LLMs read and follow hidden instructions in tool metadata
- MCP tool attack surface and trust boundaries

**Start with**: `cd labs/lab02-mcp-toolinjection/README.md`

## Setting Up Ollama (for Labs 04+)

Labs 01-03 run without Ollama. Starting from Lab 04, you'll need the Ollama infrastructure:

```bash
cd infrastructure
docker compose up -d
docker compose ps               # wait for "healthy"
docker exec -it mcp-ollama ollama pull qwen3:8b
docker exec -it mcp-ollama ollama list
```

Labs join the `mcp-network` as external networks to reach Ollama at `http://ollama:11434`.

## Development

- Run `uv run python3 -m app` in a lab directory
- Session logs are saved to `logs/{session_id}.json`
- Logs are git-ignored (not committed)

## Learning Path

1. **Lab 01**: MCP protocol fundamentals, tool discovery, real LLM integration
2. **Lab 02**: MCP security vulnerabilities — prompt injection via tool descriptions
3. **Lab 02 Audit**: Audit lab02-mcp-toolinjection — find vulnerabilities, map to OWASP/MITRE ATLAS
4. **Lab 03**: MCP with external resources (filesystem, databases)
5. **Lab 04+**: Advanced LLM tool-calling patterns and validation