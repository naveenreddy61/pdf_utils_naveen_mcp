"""FastHTML Web Application for PDF Utilities."""

import asyncio
import uvicorn
from fasthtml.common import *
from config import UPLOAD_DIR, SERVER_PORT
from src.web_app.ui.styles import CSS_STYLES
from src.web_app.services.cleanup import daily_cleanup

# Import route setup functions
from src.web_app.routes import main as main_routes
from src.web_app.routes import pdf as pdf_routes
from src.web_app.routes import api as api_routes


def create_app():
    """Create and configure the FastHTML application."""
    # Create upload directory if it doesn't exist
    UPLOAD_DIR.mkdir(exist_ok=True)
    
    # Initialize FastHTML app
    app, rt = fast_app(
        static_path='uploads',
        hdrs=(
            Link(rel='stylesheet', href='https://cdn.jsdelivr.net/npm/normalize.css@8.0.1/normalize.min.css'),
            Script(src="https://unpkg.com/htmx.org@2.0.0"),
            Style(CSS_STYLES)
        )
    )
    
    # Setup routes
    main_routes.setup_routes(app, rt)
    pdf_routes.setup_routes(app, rt)
    api_routes.setup_routes(app, rt)
    
    # Start background cleanup task when the app starts
    @app.on_event("startup")
    async def startup_event():
        """Start background tasks on app startup."""
        print("=== PDF WEB APP STARTUP ===", flush=True)
        print(f"Upload directory: {UPLOAD_DIR.resolve()}", flush=True)
        print(f"Upload directory exists: {UPLOAD_DIR.exists()}", flush=True)
        print(f"Static files served from: uploads/", flush=True)
        print("=== STARTUP COMPLETE ===", flush=True)
        asyncio.create_task(daily_cleanup())
    
    return app


def serve(app, port=None):
    """Serve the FastHTML application."""
    if port is None:
        port = SERVER_PORT
    uvicorn.run(app, host="0.0.0.0", port=port)