"""
Entry point — run as:
    python -m liteparse_mcp                    # stdio (Claude Desktop / Claude Code)
    python -m liteparse_mcp --http             # HTTP/SSE on http://0.0.0.0:8765
    python -m liteparse_mcp --http --port 3000 # custom port
    liteparse-mcp                              # after pip install (console_scripts)

When deployed on Render/Fly.io the $PORT environment variable is respected
automatically via the Dockerfile; you can also pass --port explicitly.
"""

import os
import sys

# Import tools module to trigger @mcp.tool registrations
from .tools import mcp  # noqa: F401 — side-effect import


def main() -> None:
    if "--http" in sys.argv:
        # Parse optional --port <n> argument, fall back to $PORT, then 8765
        port = int(os.environ.get("PORT", 8765))
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            try:
                port = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                pass

        # Bind to 0.0.0.0 so Render / Docker can route traffic in
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
