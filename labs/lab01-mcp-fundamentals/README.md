# lab01-mcp-fundamentals — MCP Fundamentals

This lab demonstrates the basic Model Context Protocol (MCP) flow with real LLM integration:
- An **MCP Client** (interactive CLI `app.py`) that starts an **MCP Server** via stdin/stdout
- The client registers the server's tools via JSON-RPC 2.0
- Real LLM integration using Ollama (`qwen3:8b`) — user prompts are sent to the LLM,
  which decides whether to invoke a tool based on the available tools
- Tool communication is displayed in real time with `[MCP Client -> MCP Server]` prefixes
- The client has a built-in `echo` tool; after registration, the server's `read_security_message` tool is available
- Full MCP protocol handshake visible in logs

## Structure

```
labs/lab01-mcp-fundamentals/
├── app.py                     # Interactive MCP Client (renamed from demo_client.py)
├── mcp_server.py              # MCP Server (renamed from demo_server.py)
├── data/
│   └── security.txt           # Security message read by the server tool
├── logs/                      # Session logs (auto-generated, not in git)
│   └── {session_id}.json      # One JSON file per session
├── pyproject.toml             # uv project config
└── README.md                  # This file
```

## Session Logging

Each interactive session is logged to a JSON file in the `logs/` folder.
- **Filename**: `{session_id}.json` (UUID generated per session)
- **Format**: JSON Lines (one JSON object per line)
- **Fields per entry**:
  - `timestamp`: ISO 8601 UTC timestamp
  - `session_id`: Unique session identifier
  - `model`: LLM model used (e.g., `qwen3:8b`)
  - `user_prompt`: The user's input prompt
  - `response`: LLM's response (tool execution result or text)
  - `turn`: Turn number within the session

Example log entry:
```json
{"timestamp": "2026-10-05T20:58:19.131355+00:00", "session_id": "4cc49935-3074-4b9b-9aa0-af7b51f44b94", "model": "qwen3:8b", "user_prompt": "read_security_message", "response": "Tool [read_security_message] executed: Good job, you are implementing a MCP Server", "turn": 1}
```

> **Note**: The `logs/` folder is in `.gitignore` — session logs are never committed to git.

## Quick Start

```bash
cd labs/lab01-mcp-fundamentals

# Main command — runs the interactive MCP Client
uv run python3 -m app

# Or run directly with python3
python3 app.py
```

The MCP Server is **started automatically** when you type `/register` in the app. It is **real** (not simulated) — the app launches `mcp_server.py` as a subprocess, speaks JSON-RPC 2.0 over stdin/stdout, and the communication is shown with `[MCP Client -> MCP Server]` logs.

## Interactive Session Example

```
=== lab01-mcp-fundamentals MCP Client ===
  Commands: /help, /tools, /register, /exit
  Or type a user prompt, e.g.: echo Hola
  Press Ctrl+C to quit

> /register
[APP] Registering MCP Server (stdio transport)...
[APP] MCP Server started as subprocess (stdio).
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"id":1,"jsonrpc":"2.0","method":"initialize","params":{"capabilities":{},"clientInfo":{"name":"lab01-mcp-client","version":"1.0.0"},"protocolVersion":"2026-07-28"}}
[MCP CLIENT -> MCP SERVER] < from MCP SERVER > {"id":1,"jsonrpc":"2.0","result":{"capabilities":{"prompts":{},"resources":{},"tools":{}},"protocolVersion":"2026-07-28","serverInfo":{"name":"mcp-security-server","version":"1.0.0"}}}
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"jsonrpc":"2.0","method":"notifications/initialized"}
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"id":2,"jsonrpc":"2.0","method":"tools/list"}
[MCP CLIENT -> MCP SERVER] < from MCP SERVER > {"id":2,"jsonrpc":"2.0","result":{"tools":[{"description":"Read the security message from data/security.txt","inputSchema":{"additionalProperties":false,"properties":{},"type":"object"},"name":"read_security_message"}]}}
[APP] Tool registered: read_security_message
[APP] MCP Server registered. New tools: 1. Total tools now: 2

> /tools
[APP] Registered tools:
  - echo: Echo the user message at the screen. Useful to check that the client is working.
  - read_security_message: Read the security message from data/security.txt

> echo Hola
[LLM] LLM decided to invoke tool(s).
[APP] Tool [echo] executed. Result:
    Echo: Hola

> read_security_message
[LLM] LLM decided to invoke tool(s).
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"id":1,"jsonrpc":"2.0","method":"initialize","params":{"capabilities":{},"clientInfo":{"name":"lab01-mcp-client","version":"1.0.0"},"protocolVersion":"2026-07-28"}}
[MCP CLIENT -> MCP SERVER] < from MCP SERVER > {"id":1,"jsonrpc":"2.0","result":{"capabilities":{"prompts":{},"resources":{},"tools":{}},"protocolVersion":"2026-07-28","serverInfo":{"name":"mcp-security-server","version":"1.0.0"}}}
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"jsonrpc":"2.0","method":"notifications/initialized"}
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"id":2,"jsonrpc":"2.0","method":"tools/call","params":{"arguments":{},"name":"read_security_message"}}
[MCP CLIENT -> MCP SERVER] < from MCP SERVER > {"id":2,"jsonrpc":"2.0","result":{"content":[{"text":"Good job, you are implementing a MCP Server","type":"text"}]}}
[APP] Tool [read_security_message] executed. Result:
    Good job, you are implementing a MCP Server

> /exit
[APP] Goodbye!
```

## What Happens When You Run `/register`

When you type `/register` in the interactive client, the following three-step MCP handshake occurs over stdio transport:

1. **`initialize`** — The client sends an `initialize` JSON-RPC 2.0 request. The server responds with its `protocolVersion`, `serverInfo`, and declared `capabilities`. This establishes the protocol version and tells the client what the server supports.

2. **`notifications/initialized`** — The client sends a `notifications/initialized` notification (no response ID, no response expected). This acknowledges that the handshake is complete and the session is ready for tool operations.

3. **`tools/list`** — The client sends a `tools/list` request. The server responds with its available tools (e.g., `read_security_message`). The client registers these tools in its local tool registry, making them available for invocation.

### Why the handshake repeats for tool calls

The stdio transport requires the MCP Server subprocess to terminate after each registration. When a registered tool is invoked (e.g., `read_security_message`), the client must relaunch the server and repeat steps 1–3 (`initialize` → `notifications/initialized` → `tools/call`) because:

- The subprocess only lives while the stdio pipe is open
- Each tool call needs a fresh server instance with a new stdio connection
- This is why `/register` starts the server, and why invoking an MCP server tool also triggers a full handshake with a re-launched server

### Discovery vs. Call

- **Discovery** (`/register`): Runs the full `initialize` → `initialized` → `tools/list` sequence to find out what tools the server offers.
- **Tool Call**: After registration, invoking a tool (e.g., via LLM decision or `echo Hola`) relaunches the server and runs `initialize` → `initialized` → `tools/call` with the specific tool name and arguments.

After `/register`, the `/tools` command lists both the built-in `echo` tool and any MCP server tools that were discovered (e.g., `read_security_message`).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  uv run python3 -m app (app.py) — Interactive MCP Client   │
│  - Reads user input from stdin                             │
│  - Sends prompts to Ollama LLM with available tools        │
│  - Parses LLM response: tool_calls or text                │
│  - Starts MCP Server automatically on /register            │
│  - Executes tools (echo built-in or MCP server via stdio) │
│  - Shows [MCP Client -> MCP Server] communication logs    │
└─────────────────────┬─────────────────────────────────────┘
                      │ stdio (JSON-RPC 2.0)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  MCP Server (mcp_server.py) — stdio transport             │
│  - JSON-RPC 2.0 message handler                           │
│  - read_security_message tool: reads data/security.txt     │
│  - initialize / tools/list / tools/call methods           │
└─────────────────────────────────────────────────────────────┘
```

## Real LLM Integration

This lab replaces the simulated LLM with actual Ollama calls:

```
POST http://localhost:11434/api/chat
{
  "model": "qwen3:8b",
  "messages": [{"role": "user", "content": "echo Hola"}],
  "tools": [
    {"type": "function", "function": {"name": "echo", ...}},
    {"type": "function", "function": {"name": "read_security_message", ...}}
  ],
  "stream": false
}
```

Llama 3 / Qwen responses include `message.tool_calls` when the LLM decides to use a tool.
The client parses these and executes the corresponding tool.

## Supported Commands

| Command | Description |
|---------|-------------|
| `/help` | Show this help menu |
| `/tools` | List available tools (echo + MCP server tools) |
| `/register` | Register MCP Server via stdio (adds its tools) |
| `/exit` | Exit the interactive session |
| `echo Hola` | User prompt — LLM invokes echo tool |
| `read_security_message` | User prompt — LLM invokes server tool |

## uv Commands

```bash
cd labs/lab01-mcp-fundamentals

# Main command — runs the interactive MCP Client
uv run python3 -m app

# Alternative: run directly with python3
python3 app.py

# NOT NEEDED for normal use — the app starts the server automatically when you type /register
# uv run python3 -m mcp_server   # Runs the MCP Server directly (waits for JSON-RPC on stdin)
```

### Why `uv run python3 -m mcp_server` exists
The `mcp_server` module lets you run the server standalone for debugging or for connecting from a different client. It reads JSON-RPC from stdin and writes responses to stdout. You typically **don't need to run it manually** — the `/register` command in the app starts it as a subprocess and handles the communication.

## What You Learn

1. **MCP Protocol Handshake**: `initialize` → `notifications/initialized` → `tools/list`
2. **Tool Registration**: The client discovers server tools and adds them to its local registry
3. **LLM Integration Pattern**: The LLM (Ollama qwen3:8b) sees available tool definitions and decides which to invoke based on the user prompt
4. **Real Tool Execution**: Tools are executed via JSON-RPC 2.0 over stdio — either built-in `echo` or MCP server tools like `read_security_message`
5. **Communication Visualization**: All JSON-RPC messages are displayed with `[MCP Client -> MCP Server]` prefix
6. **Security Message**: The server reads a file from `data/security.txt` to prove file access via MCP tools
exit
## Next Steps

This lab establishes the MCP fundamentals with real LLM integration. Later labs will explore:
- **lab02**: MCP security vulnerabilities (prompt injection, tool poisoning)
- **lab03**: MCP with external resources (filesystem, databases)
- **lab04+**: More advanced LLM tool-calling patterns and validation