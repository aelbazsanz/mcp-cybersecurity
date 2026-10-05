# Lab 01: MCP Fundamentals

## Objective

Understand how the Model Context Protocol (MCP) works. MCP is a protocol that
lets an application communicate with external data sources (like a database,
file system, or API) through an **MCP Server**, using messages in **JSON-RPC**
format.

This lab does **not** require Ollama (or any LLM). It focuses on the protocol
itself — the discovery, request, and response flow — so you can see the
mechanism clearly without the LLM layer in the way.

## How MCP Works (The Big Picture)

```
[APP] ── JSON-RPC ──► [MCP CLIENT] ── JSON-RPC ──► [MCP SERVER] ── query ──► [DATA SOURCE]
  ▲                                                                                │
  └────────────────────────────────────────────────────────────────────────────────┘
```

1. **The app** (e.g., a chat interface) wants to talk to an external data source.
2. **The MCP Client** is the part of the app that speaks JSON-RPC. It sends
   requests to the MCP Server.
3. **The MCP Server** is a bridge between the client and the actual data source.
   It translates JSON-RPC requests into queries against the data source.
4. **The data source** (database, file, API, etc.) returns raw data.
5. **The MCP Server** wraps the data into a JSON-RPC response and sends it back
   to the client.
6. **The app** receives the data and can display it to the user.

## Discovery / Registration

When the app starts, it needs to know which MCP Servers are available. This is
the **discovery** step:

- The MCP Client asks the MCP Server what it can do (`initialize` / `ping`).
- The server replies with its **capabilities** — what tools, resources, and
  prompts it offers.
- The app registers the server so it can call its tools later.

In this lab's demo, you will see this discovery step happen automatically before
any data is requested.

## Message Format

MCP uses **JSON-RPC 2.0**. Every message is a JSON object:

**Request** (Client → Server):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": { "name": "query_db", "arguments": { "query": "SELECT * FROM users" } }
}
```

**Response** (Server → Client):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": { "content": [{ "type": "text", "text": "[... data ...]" }] }
}
```

**Notification** (one-way, no response expected):
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

## Running the Demo

This lab contains two scripts that together show the full flow:

- `demo_server.py` — runs the MCP Server (bridges JSON-RPC ↔ data source)
- `demo_client.py` — runs the MCP Client inside the app (talks JSON-RPC)

They communicate over **stdio** (standard input/output), which is the simplest
MCP transport — no network, no ports, just pipes.

### Step 1: Start the server (in one terminal)

```bash
python demo_server.py
```

The server will start, listen on stdin/stdout, and wait for JSON-RPC messages.

### Step 2: Run the client (in another terminal)

```bash
python demo_client.py
```

The client will:
1. **Discover** the server (send `initialize`, receive capabilities)
2. **Call a tool** (send `tools/call` to query the database)
3. **Receive** the data and display it

Each line of output is tagged with its source so you can see exactly who is
speaking: `[APP]`, `[MCP CLIENT]`, `[MCP SERVER]`, or `[DATA SOURCE]`.

## What to Look For

- The **discovery handshake** at the start (client asks, server answers).
- The **JSON-RPC envelope** on every message (`jsonrpc`, `id`, `method`,
  `params` / `result`).
- The **source tags** that show the direction of every message.
- How the server translates a JSON-RPC request into a query against the data
  source, and wraps the result back into JSON-RPC.

## Next Steps

After you understand the protocol flow, later labs will add:
- A real LLM (Ollama) that decides *when* to call an MCP tool.
- Real MCP servers (filesystem, database, web search).
- Security considerations (tool permission, input validation, prompt
  injection).