"""API routes for the web application."""

from fasthtml.common import *
from web_app.services.cleanup import cleanup_old_files
from web_app.ui.components import success_message, error_message


def setup_routes(app, rt):
    """Set up API routes."""
    
    @rt('/cleanup')
    async def manual_cleanup():
        """Manual trigger for cleanup (protected endpoint)."""
        # In production, this should be protected with authentication
        # For now, it's a simple endpoint for testing
        try:
            deleted_count = await cleanup_old_files()
            return Div(
                success_message(f"Cleanup completed. Deleted {deleted_count} old files.")
            )
        except Exception as e:
            return Div(
                error_message(f"Error during cleanup: {str(e)}")
            )