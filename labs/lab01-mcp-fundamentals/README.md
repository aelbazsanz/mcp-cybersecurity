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
├── pyproject.toml             # uv project config
└── README.md                  # This file
```

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

## How It Works

1. **Start**: Run `uv run app` (or `python3 app.py`) — shows the interactive menu
2. **`/register`**: The app starts the MCP Server as a **real subprocess** and speaks JSON-RPC 2.0 to it:
   - `initialize` → server responds with capabilities
   - `notifications/initialized` → acknowledges session readiness
   - `tools/list` → discovers server tools (e.g., `read_security_message`)
3. **After registration**: `/tools` lists both the built-in `echo` and MCP server tools
4. **User prompts**: e.g., `echo Hola`, `read_security_message`
   - The prompt is sent to the LLM (Ollama `qwen3:8b`) along with available tools
   - The LLM decides which tool to invoke (or returns text)
   - If tool calls: the MCP Server is started again, the tool is called via JSON-RPC 2.0, result is shown
   - If text: the LLM's response is shown
5. **Communication logs**: All JSON-RPC messages are prefixed with `[MCP Client -> MCP Server]` and also saved to `.mcp_client_logs.txt`

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
```

## Next Steps

This lab establishes the MCP fundamentals with real LLM integration. Later labs will explore:
- **lab02**: MCP security vulnerabilities (prompt injection, tool poisoning)
- **lab03**: MCP with external resources (filesystem, databases)
- **lab04+**: More advanced LLM tool-calling patterns and validation