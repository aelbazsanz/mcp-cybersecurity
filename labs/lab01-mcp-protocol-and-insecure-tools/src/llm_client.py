"""LLM Client module — talks to Ollama (the local model server).

This is the "LLM side" of the Host. It sends a chat request to Ollama over
HTTP and, if the model asks to call a tool, the app (Host) routes the request
through the MCP Client to the MCP Server. This module does NOT know about MCP
tools — the app converts them into Ollama function calls.

Flow annotations are printed on every message so you can see exactly who
talks to whom: [APP → LLM Client], [LLM Client → Ollama], etc.
"""
import json
import urllib.request
from typing import Any


class LLMClient:
    """Minimal Ollama HTTP client with tool-calling support."""

    def __init__(self, url: str, model: str):
        self._url = url.rstrip("/")
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @staticmethod
    def mcp_tools_to_ollama(tools: list[dict]) -> list[dict]:
        """Convert MCP tool metadata to Ollama function-call format.

        MCP:  {"name": "read_resource", "description": "...", "inputSchema": {...}}
        Ollama: {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
        """
        out = []
        for t in tools:
            out.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            })
        return out

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Send a chat request to Ollama and return the response dict.

        Returns the raw Ollama response, which may contain 'message.tool_calls'.
        """
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        print(f"[APP → LLM Client] chat(model={self._model}, messages={len(messages)})")
        if tools:
            print(f"[APP → LLM Client] available tools: {[t['function']['name'] for t in tools]}")
        print(f"[LLM Client → Ollama] POST {self._url}/api/chat")
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self._url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        msg = raw.get("message", {})
        print(f"[Ollama → LLM Client] reply: {json.dumps(msg, ensure_ascii=False)[:300]}")
        return msg

    def chat_loop(self, system: str, user: str, tools: list[dict] | None,
                  tool_runner) -> str:
        """Run a tool-calling loop until the model stops requesting tools.

        tool_runner is a callable(tool_name, arguments) -> str that the app
        provides (it routes the call through the MCP Client).
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        print(f"[APP → LLM Client] Start chat loop (system={system!r})")
        max_turns = 10  # safety limit to prevent infinite loops
        for turn in range(max_turns):
            msg = self.chat(messages, tools)
            messages.append(msg)
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                print(f"[LLM Client → APP] Final answer: {msg.get('content', '')}")
                return msg.get("content", "")
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args) if args else {}
                print(f"[APP → LLM Client] Model wants to call tool: {name}({args})")
                result = tool_runner(name, args)
                messages.append({
                    "role": "tool",
                    "content": result,
                })
        print(f"[LLM Client → APP] Stopped after {max_turns} turns (safety limit)")
        return "Stopped after too many turns."