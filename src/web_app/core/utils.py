"""Utility functions for the web application."""

import asyncio
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


def _count_tokens_sync(text: str) -> int:
    """Synchronous token counting helper (CPU-bound operation)."""
    encoding = tiktoken.encoding_for_model(TOKEN_COUNTING_MODEL)
    return len(encoding.encode(text))


async def count_tokens(text: str) -> int:
    """Count tokens in text using GPT-4o encoding.

    Runs the CPU-bound token counting in a thread pool to avoid blocking the event loop.
    This ensures other requests can be processed while counting tokens.
    """
    return await asyncio.to_thread(_count_tokens_sync, text)