"""Database models and operations for PDF files."""

from dataclasses import dataclass
from datetime import datetime
from fastlite import database
from apswutils.db import NotFoundError
from config import DB_PATH


@dataclass
class FileRecord:
    file_hash: str  # Primary key
    original_filename: str
    stored_filename: str
    file_size: int
    page_count: int
    upload_date: str
    last_accessed: str


@dataclass
class SettingsRecord:
    id: int  # Primary key (always 1 for single settings record)
    gemini_api_key: str = ""  # User-provided API key (empty means use env var)
    ocr_model: str = "gemini-2.5-flash-lite"  # Selected OCR model
    updated_at: str = ""


# Ensure data directory exists
DB_PATH.parent.mkdir(exist_ok=True)

# Initialize database
db = database(str(DB_PATH))
files = db.create(FileRecord, pk='file_hash')
settings = db.create(SettingsRecord, pk='id')


def get_file_info(file_hash: str):
    """Get file info from database, returns None if not found."""
    try:
        return files.get(file_hash)
    except NotFoundError:
        return None


def update_last_accessed(file_hash: str):
    """Update the last accessed timestamp for a file."""
    files.update({'last_accessed': datetime.now().isoformat()}, file_hash)


def insert_file_record(file_record: FileRecord):
    """Insert a new file record into the database."""
    files.insert(file_record)


def delete_file_record(file_hash: str):
    """Delete a file record from the database."""
    files.delete(file_hash)


def get_old_files(cutoff_date: datetime):
    """Get files older than the cutoff date."""
    cutoff_str = cutoff_date.isoformat()
    return files(where=f"upload_date < '{cutoff_str}'")


def get_settings():
    """Get user settings, returns default if not found."""
    try:
        return settings.get(1)
    except NotFoundError:
        # Create default settings
        default_settings = SettingsRecord(
            id=1,
            gemini_api_key="",
            ocr_model="gemini-2.5-flash-lite",
            updated_at=datetime.now().isoformat()
        )
        settings.insert(default_settings)
        return default_settings


def update_settings(gemini_api_key: str = None, ocr_model: str = None):
    """Update user settings."""
    current = get_settings()
    updates = {'updated_at': datetime.now().isoformat()}

    if gemini_api_key is not None:
        updates['gemini_api_key'] = gemini_api_key
    if ocr_model is not None:
        updates['ocr_model'] = ocr_model

    settings.update(updates, 1)
    return get_settings()