"""Session-based settings management for ephemeral API key and model storage."""

from typing import Optional, List, Dict
from config import OCR_MODEL


def get_session_settings(session: dict) -> dict:
    """
    Get settings from session with defaults.

    Args:
        session: FastHTML session dict

    Returns:
        dict with gemini_api_key, ocr_model, and available_models
    """
    settings = {
        'gemini_api_key': session.get('gemini_api_key', ''),
        'ocr_model': session.get('ocr_model', OCR_MODEL),
        'available_models': session.get('available_models', [])
    }

    # Debug logging
    print(f"[DEBUG] get_session_settings called")
    print(f"[DEBUG] Session keys: {list(session.keys())}")
    print(f"[DEBUG] gemini_api_key present: {bool(settings['gemini_api_key'])}")
    print(f"[DEBUG] ocr_model: {settings['ocr_model']}")
    print(f"[DEBUG] available_models count: {len(settings['available_models'])}")

    return settings


def update_session_settings(session: dict, gemini_api_key: Optional[str] = None, ocr_model: Optional[str] = None) -> dict:
    """
    Update session settings.

    Args:
        session: FastHTML session dict
        gemini_api_key: Optional API key (None to skip update, empty string to clear)
        ocr_model: Optional model name

    Returns:
        Updated settings dict
    """
    print(f"[DEBUG] update_session_settings called")
    print(f"[DEBUG] Updating API key: {gemini_api_key is not None}")
    print(f"[DEBUG] Updating model: {ocr_model}")

    if gemini_api_key is not None:
        session['gemini_api_key'] = gemini_api_key
        print(f"[DEBUG] Set gemini_api_key in session")

    if ocr_model is not None:
        session['ocr_model'] = ocr_model
        print(f"[DEBUG] Set ocr_model to: {ocr_model}")

    # Force session modification flag for Starlette
    if hasattr(session, 'modified'):
        session.modified = True
        print(f"[DEBUG] Session modified flag set")

    return get_session_settings(session)


def save_available_models(session: dict, models: List[Dict]) -> None:
    """
    Save the list of available models to session.

    Args:
        session: FastHTML session dict
        models: List of model dictionaries
    """
    print(f"[DEBUG] save_available_models called with {len(models)} models")
    session['available_models'] = models

    # Force session modification flag for Starlette
    # This ensures the session is saved after the request
    if hasattr(session, 'modified'):
        session.modified = True

    print(f"[DEBUG] Saved available_models to session")
    print(f"[DEBUG] Session modified flag set: {getattr(session, 'modified', False)}")
    print(f"[DEBUG] Session now has keys: {list(session.keys())}")


def clear_session_settings(session: dict):
    """Clear all settings from session."""
    session.pop('gemini_api_key', None)
    session.pop('ocr_model', None)
    session.pop('available_models', None)
