"""Lab01 App — the MCP Host that orchestrates the full architecture.

Architecture layers:
  ┌─────────────────────────────────────────────────────────────────┐
  │                        HOST (app)                               │
  │                                                                 │
  │  ┌─────────────────────────────────────────────────────────┐   │
  │  │                      app.py                             │   │
  │  │  1. Creates MCPClient + LLMClient                       │   │
  │  │  2. MCPClient does initialize handshake with server     │   │
  │  │  3. MCPClient discovers tools (tools/list)              │   │
  │  │  4. App offers those tools to the LLM                   │   │
  │  │  5. LLM requests a tool → app routes via MCPClient      │   │
  │  │  6. MCPClient → MCP Server (tools/call) → result        │   │
  │  │  7. App returns result to LLM, gets final answer        │   │
  │  └─────────────────────────────────────────────────────────┘   │
  │                         │                                       │
  │      ┌──────────────────▼─────────────────┐   ┌──────────────┐  │
  │      │    MCP Client  (mcp_client.py)     │   │ LLM Client   │  │
  │      │  - JSON-RPC over stdio             │   │ (llm_client) │  │
  │      │  - initialize / tools/list         │   │  - HTTP POST │  │
  │      │  - tools/call                      │   │  - tool loop │  │
  │      └───────────────┬────────────────────┘   └──────┬───────┘  │
  │                      │ stdio                        │ HTTP      │
  │      ┌───────────────▼────────────────────┐   ┌──────▼───────┐  │
  │      │        MCP Server                  │   │   Ollama     │  │
  │      │  server_vulnerable.py /            │   │  (infra/     │  │
  │      │  server_secure.py                  │   │  docker)     │  │
  │      └────────────────────────────────────┘   └──────────────┘  │
  └─────────────────────────────────────────────────────────────────┘

The "how does the app know it has an MCP client?" answer:
  import mcp_client
  mcp = mcp_client.MCPClient(server_path, label)
  mcp.connect()           # handshake + discovery
  tools = mcp.list_tools()  # app now knows what the server provides
  mcp.call_tool(...)        # app invokes tools on the server

No hidden registration/discovery — the app explicitly creates and uses the client.
"""
import argparse
import os
import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB_DIR / "src"))

from mcp_client import MCPClient
from llm_client import LLMClient


SERVERS = {
    "secure": LAB_DIR / "src" / "server_secure.py",
    "vulnerable": LAB_DIR / "src" / "server_vulnerable.py",
}


def scenario_tools(server_key: str) -> None:
    """Scenario 1: Just MCP tools (no LLM).

    Demonstrates the pure MCP protocol:
    1. Connect to server (handshake + discovery)
    2. List available tools
    3. Call a tool directly
    """
    print("\n" + "=" * 60)
    print("SCENARIO: Tools only (no LLM)")
    print("=" * 60)

    server_path = SERVERS[server_key]
    print(f"\n[APP] Creating MCP Client for {server_key} server")
    client = MCPClient(server_path=str(server_path), label=server_key)

    try:
        client.connect()
        tools = client.list_tools()
        print(f"\n[APP] Available tools from {server_key} server:")
        for t in tools:
            print(f"  • {t['name']}: {t.get('description', 'No description')}")

        # Call a simple tool
        print(f"\n[APP] Calling get_user_name tool...")
        result = client.call_tool("get_user_name", {})
        print(f"[APP] Tool result: {result}")

        # Show resources
        resources = client.list_resources()
        if resources:
            print(f"\n[APP] Available resources:")
            for r in resources:
                print(f"  • {r.get('name', r.get('uri'))}: {r.get('description', 'No description')}")
            print(f"\n[APP] Reading resource://notes/welcome.md...")
            content = client.read_resource("resource://notes/welcome.md")
            print(f"[APP] Resource content: {content!r}")

    finally:
        client.close()


def scenario_chat(server_key: str, ollama_url: str, model: str) -> None:
    """Scenario 2: MCP tools + LLM chat (full tool-calling loop).

    Demonstrates the complete Host → Client → Server + LLM flow:
    1. Connect to MCP server (handshake + tool discovery)
    2. Convert MCP tools to Ollama function format
    3. Send a user request to the LLM with tool definitions
    4. If LLM calls a tool, route it through MCPClient to the server
    5. Return tool result to LLM, get final answer
    """
    print("\n" + "=" * 60)
    print("SCENARIO: Chat with tools (MCP + LLM)")
    print("=" * 60)

    server_path = SERVERS[server_key]
    print(f"\n[APP] Creating MCP Client for {server_key} server")
    mcp_client = MCPClient(server_path=str(server_path), label=server_key)

    print(f"[APP] Creating LLM Client (Ollama at {ollama_url}, model={model})")
    llm_client = LLMClient(url=ollama_url, model=model)

    try:
        # 1. Connect to MCP server and discover tools
        mcp_client.connect()
        mcp_tools = mcp_client.list_tools()
        print(f"\n[APP] Tools discovered from server: {[t['name'] for t in mcp_tools]}")

        # 2. Convert to Ollama function format
        ollama_tools = LLMClient.mcp_tools_to_ollama(mcp_tools)

        # 3. Define the tool runner that the app provides to the LLM loop
        def tool_runner(name: str, args: dict) -> str:
            """App routes LLM's tool call → MCP Client → MCP Server."""
            print(f"[APP → MCP Client] Routing tool call: {name}({args})")
            return mcp_client.call_tool(name, args)

        # 4. Start the chat loop
        system_prompt = (
            "You are a helpful assistant that can read notes using the available tools. "
            "Use the tools when the user asks about notes or resources."
        )
        user_prompt = (
            "What notes do you have available? Please read them and summarize."
        )
        print(f"\n[APP] Sending user request to LLM...")
        final_answer = llm_client.chat_loop(system_prompt, user_prompt, ollama_tools, tool_runner)
        print(f"\n[APP] ===== LLM Final Answer =====")
        print(final_answer)
        print(f"[APP] =============================")

    except ConnectionError as e:
        print(f"\n[APP] Error: {e}")
        print(f"[APP] Tip: Start Ollama with: docker compose -f ../../infrastructure/docker-compose.yml up -d")
        sys.exit(1)
    finally:
        mcp_client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lab01 App - MCP Architecture Demo (Host → Client → Server + LLM)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pure MCP protocol (no LLM needed)
  uv run python src/app.py --scenario tools --server secure
  uv run python src/app.py --scenario tools --server vulnerable

  # With LLM (requires Ollama running)
  docker compose -f ../../infrastructure/docker-compose.yml up -d
  docker exec -it mcp-ollama ollama pull llama3
  uv run python src/app.py --scenario chat --server secure
        """
    )
    parser.add_argument(
        "--scenario",
        choices=["tools", "chat"],
        default="tools",
        help="Scenario to run: 'tools' (MCP only) or 'chat' (MCP + Ollama)",
    )
    parser.add_argument(
        "--server",
        choices=["secure", "vulnerable"],
        default="secure",
        help="Which MCP server to connect to",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        help="Ollama URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", "llama3"),
        help="LLM model name (default: llama3)",
    )

    args = parser.parse_args()

    if args.scenario == "tools":
        scenario_tools(args.server)
    elif args.scenario == "chat":
        scenario_chat(args.server, args.ollama_url, args.model)

    return 0


if __name__ == "__main__":
    sys.exit(main())