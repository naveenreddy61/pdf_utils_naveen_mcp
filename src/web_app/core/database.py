"""Database models and operations for PDF files."""

from dataclasses import dataclass
from datetime import datetime
from fastlite import database
from apswutils.db import NotFoundError
from pdf_utils.config import DB_PATH


@dataclass
class FileRecord:
    file_hash: str  # Primary key
    original_filename: str
    stored_filename: str
    file_size: int
    page_count: int
    file_type: str  # 'pdf' or 'image'
    upload_date: str
    last_accessed: str


# Ensure data directory exists
DB_PATH.parent.mkdir(exist_ok=True)

# Initialize database
db = database(str(DB_PATH))
files = db.create(FileRecord, pk='file_hash')


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