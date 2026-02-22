#!/usr/bin/env python3
"""Command-line entry point for PDF Web Application.

Usage:
    pdf-web-app              # Start on default port 8000
    pdf-web-app --port 9000  # Start on custom port
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv


def validate_environment() -> bool:
    """Check for API key and provide helpful guidance.

    Returns:
        True if API key found, False otherwise
    """
    load_dotenv()

    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("━" * 70, file=sys.stderr)
        print("⚠️  WARNING: No Gemini API key found", file=sys.stderr)
        print("", file=sys.stderr)
        print("OCR features require a Google Gemini API key.", file=sys.stderr)
        print("Basic PDF operations (TOC, pages, images) will still work.", file=sys.stderr)
        print("", file=sys.stderr)
        print("To enable OCR:", file=sys.stderr)
        print("  1. Get API key: https://aistudio.google.com/app/apikey", file=sys.stderr)
        print("  2. Set environment variable:", file=sys.stderr)
        print("     export GOOGLE_API_KEY='your-key-here'", file=sys.stderr)
        print("     (or use GEMINI_API_KEY)", file=sys.stderr)
        print("", file=sys.stderr)
        print("  3. Restart the application", file=sys.stderr)
        print("━" * 70, file=sys.stderr)
        print("", file=sys.stderr)
        return False

    return True


def main():
    """Main entry point for the PDF Web Application."""
    parser = argparse.ArgumentParser(
        description="PDF & Image Processing Web Application with Gemini OCR",
        epilog="Visit http://localhost:8000 after starting the server"
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=None,
        help='Port to run server on (default: 8000 from config)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default="0.0.0.0",
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--no-api-key-check',
        action='store_true',
        help='Skip API key validation (for testing)'
    )

    args = parser.parse_args()

    # Validate environment
    if not args.no_api_key_check:
        has_api_key = validate_environment()
        if has_api_key:
            print("✓ Gemini API key detected", file=sys.stderr)
            print("", file=sys.stderr)

    # Import app after env validation (allows early exit if needed)
    from web_app.app import create_app, serve
    from pdf_utils.config import SERVER_PORT

    port = args.port if args.port is not None else SERVER_PORT

    print("=" * 70)
    print("🚀 PDF Web Application Starting")
    print("=" * 70)
    print(f"📂 Upload directory: uploads/")
    print(f"🌐 Server URL: http://{args.host}:{port}")
    print(f"📖 Features: TOC extraction, page extraction, image conversion, text OCR")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 70)
    print("")

    try:
        app = create_app()
        serve(app, port=port)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
