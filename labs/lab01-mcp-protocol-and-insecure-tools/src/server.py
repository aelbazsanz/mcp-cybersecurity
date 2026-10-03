"""VULNERABLE MCP server (lab01).

For educational use only, inside an isolated container (no network).
It contains two deliberate flaws:
  - read_note:    path traversal       (CWE-22)
  - search_notes: command injection    (CWE-78)

IMPORTANT: with the stdio transport, stdout is the protocol channel.
Never use print() here; any debug output must go to stderr.
"""
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NOTES_DIR = DATA_DIR / "notes"

mcp = FastMCP("notes-vulnerable")


@mcp.tool()
def list_notes() -> list[str]:
    """List the names of the available notes."""
    return sorted(p.name for p in NOTES_DIR.iterdir())


@mcp.tool()
def read_note(name: str) -> str:
    """Read the contents of a note by its name (e.g. 'welcome.md')."""
    # VULNERABLE: 'name' is not validated; '../secret.txt' or an absolute path escapes NOTES_DIR.
    return (NOTES_DIR / name).read_text()


@mcp.tool()
def search_notes(keyword: str) -> str:
    """Search the notes for a keyword and return the files that contain it."""
    # VULNERABLE: 'keyword' is interpolated into a shell command line.
    result = subprocess.run(
        f"grep -ril {keyword} {NOTES_DIR}",
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout or "no results"


if __name__ == "__main__":
    mcp.run(transport="stdio")
