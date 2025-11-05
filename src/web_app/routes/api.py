"""API routes for the web application."""

import os
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import JSONResponse
from google import genai
from src.web_app.services.cleanup import cleanup_old_files
from src.web_app.ui.components import success_message, error_message
from src.web_app.core.database import get_settings, update_settings


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

    @rt('/api/models/list')
    async def list_gemini_models(request: Request):
        """Fetch available Gemini models from the API."""
        try:
            # Get API key from settings or environment
            user_settings = get_settings()
            api_key = user_settings.gemini_api_key or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')

            if not api_key:
                return JSONResponse({
                    "error": "No API key configured. Please set GOOGLE_API_KEY environment variable or configure in settings."
                }, status_code=400)

            # Initialize client with user's API key
            client = genai.Client(api_key=api_key)

            # Fetch models
            models_list = []
            models = client.models.list()

            for model in models.items:
                # Only include models that support generateContent
                if "generateContent" in model.supported_actions:
                    models_list.append({
                        "name": model.name,
                        "display_name": model.display_name,
                        "description": model.description or "",
                        "input_token_limit": model.input_token_limit,
                        "output_token_limit": model.output_token_limit
                    })

            return JSONResponse({
                "models": models_list,
                "count": len(models_list)
            })

        except Exception as e:
            return JSONResponse({
                "error": f"Failed to fetch models: {str(e)}"
            }, status_code=500)

    @rt('/api/settings', methods=['GET'])
    async def get_user_settings():
        """Get current user settings."""
        try:
            user_settings = get_settings()
            # Don't expose full API key, just indicate if it's set
            has_custom_key = bool(user_settings.gemini_api_key)
            has_env_key = bool(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))

            return JSONResponse({
                "has_custom_api_key": has_custom_key,
                "has_env_api_key": has_env_key,
                "ocr_model": user_settings.ocr_model,
                "updated_at": user_settings.updated_at
            })
        except Exception as e:
            return JSONResponse({
                "error": f"Failed to get settings: {str(e)}"
            }, status_code=500)

    @rt('/api/settings', methods=['POST'])
    async def save_user_settings(request: Request):
        """Save user settings."""
        try:
            data = await request.json()

            gemini_api_key = data.get('gemini_api_key')
            ocr_model = data.get('ocr_model')

            # Update settings
            updated = update_settings(
                gemini_api_key=gemini_api_key,
                ocr_model=ocr_model
            )

            return JSONResponse({
                "success": True,
                "message": "Settings saved successfully",
                "ocr_model": updated.ocr_model,
                "has_custom_api_key": bool(updated.gemini_api_key)
            })

        except Exception as e:
            return JSONResponse({
                "error": f"Failed to save settings: {str(e)}"
            }, status_code=500)