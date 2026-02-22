#!/usr/bin/env python3
"""Entry point for local development.

For production use, install the package and run:
    pdf-web-app

Or with uvx:
    uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app
"""

if __name__ == "__main__":
    # Import from new CLI module
    from src.web_app.cli import main
    main()