# lab01-mcp-fundamentals — MCP Fundamentals

This lab demonstrates the basic Model Context Protocol (MCP) flow:
- An **MCP Client** (interactive CLI) that starts an **MCP Server** via stdin/stdout
- The client registers the server's tools via JSON-RPC 2.0
- Tool communication is displayed in real time with `[MCP CLIENT -> MCP SERVER]` prefixes
- The client has a built-in `echo` tool; after registration, the server's `read_security_message` tool is available

## Structure

```
labs/lab01-mcp-fundamentals/
├── demo_client.py        # Interactive MCP Client with /tools, /help, /register
├── demo_server.py        # MCP Server with read_security_message tool
├── data/
│   └── security.txt      # Security message read by the server tool
└── README.md             # This file
```

## Quick Start

```bash
cd labs/lab01-mcp-fundamentals

# Run the interactive client
python3 demo_client.py
```

## Interactive Session Example

```
=== lab01-mcp-fundamentals MCP Client ===
  Commands: /help, /tools, /register
  Or type a user prompt, e.g.: echo Hola
  Press Ctrl+C to quit

> /tools
[APP] Registered tools:
  - echo: Echo the user message at the screen. Useful to check that the client is working.

> echo Hola
[APP] User prompt: echo Hola
[LLM] I will use the echo tool to echo your message at the screen.
[APP] Tool [echo] executed. Result:
    Echo: Hola

> /register
[APP] Registering MCP Server (stdio transport)...
[APP] MCP Server started as subprocess (stdio).
[APP] Step 1/3: send initialize request to MCP Server...
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"id":1,"jsonrpc":"2.0","method":"initialize","params":{"capabilities":{},"clientInfo":{"name":"lab01-mcp-client","version":"1.0.0"},"protocolVersion":"2026-07-28"}}
[MCP CLIENT -> MCP SERVER] < from MCP SERVER > {"id":1,"jsonrpc":"2.0","result":{"capabilities":{"tools":{},"resources":{},"prompts":{}},"protocolVersion":"2026-07-28","serverInfo":{"name":"mcp-security-server","version":"1.0.0"}}}
[APP] Step 2/3: send initialized notification...
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"jsonrpc":"2.0","method":"notifications/initialized"}
[APP] Step 3/3: list tools of MCP Server...
[MCP CLIENT -> MCP SERVER] < to MCP SERVER > {"id":2,"jsonrpc":"2.0","method":"tools/list"}
[MCP CLIENT -> MCP SERVER] < from MCP SERVER > {"id":2,"jsonrpc":"2.0","result":{"tools":[{"description":"Read the security message from data/security.txt","inputSchema":{"additionalProperties":false,"properties":{},"type":"object"},"name":"read_security_message"}]}}
[APP] Tool registered: read_security_message
[APP] MCP Server registered. New tools: 1. Total tools now: 2

> /tools
[APP] Registered tools:
  - echo: Echo the user message at the screen. Useful to check that the client is working.
  - read_security_message: Read the security message from data/security.txt

> read_security_message and print
[APP] User prompt: read_security_message and print
[LLM] I will use the read_security_message tool to read the security message file.
[APP] Tool [read_security_message] executed. Result:
    Good job, you are implementing a MCP Server
```

## What You Learn

1. **MCP Client → Server Communication**: The client launches the server as a subprocess, speaks JSON-RPC 2.0 over stdin/stdout (stdio transport).
2. **Protocol Handshake**: `initialize` → `notifications/initialized` → `tools/list`
3. **Tool Registration**: The client discovers the server's tools and adds them to its local registry.
4. **LLM Integration Pattern**: The client simulates the LLM step — the LLM sees available tools, decides which to invoke, then the tool runs and returns results.
5. **Security Message**: The server reads a file from `data/security.txt` to prove file access via MCP tools.

## Architecture

```
┌─────────────────────┐       stdio (JSON-RPC 2.0)       ┌─────────────────────┐
│  MCP Client         │ ────────────────────────────────► │  MCP Server         │
│  (demo_client.py)   │                                   │  (demo_server.py)   │
│                     │                                   │                     │
│  - Interactive CLI  │ ◄──────────────────────────────── │  - read_security_   │
│  - Built-in echo    │                                   │    message tool     │
│  - Tool registry    │                                   │  - Reads data/      │
│  - Simulated LLM    │                                   │    security.txt     │
└─────────────────────┘                                   └─────────────────────┘
```

## Next Steps

This lab establishes the MCP fundamentals. Later labs will explore:
- **lab02**: MCP security vulnerabilities (prompt injection, tool poisoning)
- **lab03**: MCP with external resources (filesystem, databases)
- **lab04+**: Real LLM integration via Ollama (from `infrastructure/`)