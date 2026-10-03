"""FIXED MCP server (lab01). Same tools, same signatures, without the flaws.

Fixes:
  - read_note:    the final path is resolved and must stay inside NOTES_DIR.
  - search_notes: no shell; the search is done in Python (nothing to inject into).

Principle: tool arguments are chosen by the model (or by an attacker who
manipulates it), so the server must treat them as UNTRUSTED input.
"""
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NOTES_DIR = (DATA_DIR / "notes").resolve()

mcp = FastMCP("notes-secure")


def _safe_path(name: str) -> Path:
    path = (NOTES_DIR / name).resolve()
    if not path.is_relative_to(NOTES_DIR):
        raise ValueError("Access denied: the path is outside the notes directory")
    if not path.is_file():
        raise ValueError("Note not found")
    return path


@mcp.tool()
def list_notes() -> list[str]:
    """List the names of the available notes."""
    return sorted(p.name for p in NOTES_DIR.iterdir() if p.is_file())


@mcp.tool()
def read_note(name: str) -> str:
    """Read the contents of a note by its name (e.g. 'welcome.md')."""
    return _safe_path(name).read_text()


@mcp.tool()
def search_notes(keyword: str) -> str:
    """Search the notes for a keyword and return the files that contain it."""
    needle = keyword.lower()
    matches = [
        p.name
        for p in sorted(NOTES_DIR.iterdir())
        if p.is_file() and needle in p.read_text().lower()
    ]
    return "\n".join(matches) or "no results"


if __name__ == "__main__":
    mcp.run(transport="stdio")
