#!/usr/bin/env python3
"""PDF Utilities - Multiple Entry Points

Available commands after installation:
    pdf-web-app      - Start web interface (http://localhost:8000)
    pdf-mcp-server   - Start MCP server (for Claude Desktop)

Development commands:
    uv run app.py         - Start web app locally
    uv run pdf-mcp-server - Start MCP server locally

Quick start with uvx (no installation):
    uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app
"""


def main():
    print(__doc__)


if __name__ == "__main__":
    main()