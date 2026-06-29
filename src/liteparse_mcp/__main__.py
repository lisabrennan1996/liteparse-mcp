"""
Entry point — run as:
    python -m liteparse_mcp          # stdio (Claude Desktop / Claude Code)
    python -m liteparse_mcp --http   # HTTP/SSE on http://127.0.0.1:8765
    liteparse-mcp                    # after pip install (console_scripts)
"""

import sys

# Import tools module to trigger @mcp.tool registrations
from .tools import mcp  # noqa: F401 — side-effect import


def main() -> None:
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="127.0.0.1", port=8765)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
