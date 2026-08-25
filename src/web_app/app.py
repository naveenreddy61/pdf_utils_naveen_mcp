"""FastHTML Web Application for PDF Utilities."""

import asyncio
import os
import shutil
import uvicorn
from fasthtml.common import *
from starlette.responses import RedirectResponse
from pdf_utils.config import UPLOAD_DIR, SERVER_PORT, LOGIN_PASSWORD, SESSION_SECRET_KEY
from web_app.ui.styles import CSS_STYLES
from web_app.services.cleanup import daily_cleanup

# Import route setup functions
from web_app.routes import main as main_routes
from web_app.routes import pdf as pdf_routes
from web_app.routes import api as api_routes
from web_app.routes import url as url_routes
from web_app.routes import auth as auth_routes
from web_app.routes import epub as epub_routes
from web_app.routes import capture as capture_routes


def _auth_check(req, sess):
    """Redirect unauthenticated requests to /login. No-op if LOGIN_PASSWORD is unset."""
    if not LOGIN_PASSWORD:
        return
    if req.url.path in ('/login', '/auth', '/logout'):
        return
    if not sess.get('authenticated'):
        return RedirectResponse('/login', status_code=303)


def create_app():
    """Create and configure the FastHTML application."""
    UPLOAD_DIR.mkdir(exist_ok=True)

    app, rt = fast_app(
        secret_key=SESSION_SECRET_KEY,
        before=Beforeware(_auth_check, skip=[r'/login', r'/logout']),
        static_path='uploads',
        hdrs=(
            Link(rel='stylesheet', href='https://cdn.jsdelivr.net/npm/normalize.css@8.0.1/normalize.min.css'),
            Script(src="https://unpkg.com/htmx.org@2.0.0"),
            Style(CSS_STYLES)
        )
    )

    auth_routes.setup_routes(app, rt)
    main_routes.setup_routes(app, rt)
    pdf_routes.setup_routes(app, rt)
    api_routes.setup_routes(app, rt)
    url_routes.setup_routes(app, rt)
    epub_routes.setup_routes(app, rt)
    capture_routes.setup_routes(app, rt)
    
    # Start background cleanup task when the app starts
    @app.on_event("startup")
    async def startup_event():
        """Start background tasks on app startup."""
        print("=== PDF WEB APP STARTUP ===", flush=True)
        print(f"Upload directory: {UPLOAD_DIR.resolve()}", flush=True)
        print(f"Upload directory exists: {UPLOAD_DIR.exists()}", flush=True)
        print(f"Static files served from: uploads/", flush=True)
        try:
            from web_app.services.md_service import resolve_render_script
            script = resolve_render_script()
            print(
                f"MD renderer: {script} exists={script.is_file()} "
                f"executable={os.access(script, os.X_OK)}",
                flush=True,
            )
            print(
                f"MD tools: pandoc={shutil.which('pandoc')} "
                f"typst={shutil.which('typst')}",
                flush=True,
            )
        except Exception as exc:
            print(f"MD renderer: probe failed ({exc})", flush=True)
        print("=== STARTUP COMPLETE ===", flush=True)
        asyncio.create_task(daily_cleanup())
    
    return app


def serve(app, port=None, host="0.0.0.0"):
    """Serve the FastHTML application."""
    if port is None:
        port = SERVER_PORT
    uvicorn.run(app, host=host, port=port)