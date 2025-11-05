"""Session-based settings management for ephemeral API key and model storage."""

from typing import Optional
from config import OCR_MODEL


def get_session_settings(session: dict) -> dict:
    """
    Get settings from session with defaults.

    Args:
        session: FastHTML session dict

    Returns:
        dict with gemini_api_key and ocr_model
    """
    return {
        'gemini_api_key': session.get('gemini_api_key', ''),
        'ocr_model': session.get('ocr_model', OCR_MODEL)
    }


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
    if gemini_api_key is not None:
        session['gemini_api_key'] = gemini_api_key

    if ocr_model is not None:
        session['ocr_model'] = ocr_model

    return get_session_settings(session)


def clear_session_settings(session: dict):
    """Clear all settings from session."""
    session.pop('gemini_api_key', None)
    session.pop('ocr_model', None)
