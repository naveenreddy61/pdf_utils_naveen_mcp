#!/usr/bin/env python3
"""Entry point for the PDF Utilities Web Application."""

from src.web_app.app import create_app, serve

if __name__ == "__main__":
    app = create_app()
    serve(app)