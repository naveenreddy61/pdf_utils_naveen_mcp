"""Utility functions for the web application."""

import hashlib
import re
from pathlib import Path
import tiktoken
from config import TOKEN_COUNTING_MODEL


def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Keep only alphanumeric, dots, hyphens, and underscores
    name = Path(filename).stem
    ext = Path(filename).suffix
    safe_name = re.sub(r'[^\w\-_]', '_', name)
    return f"{safe_name}{ext}"


def count_tokens(text: str) -> int:
    """Count tokens in text using GPT-4o encoding."""
    encoding = tiktoken.encoding_for_model(TOKEN_COUNTING_MODEL)
    return len(encoding.encode(text))