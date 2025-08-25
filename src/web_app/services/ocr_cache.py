"""OCR Cache service using SQLite for storing processed OCR results."""

import sqlite3
import hashlib
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple
from contextlib import asynccontextmanager
import aiosqlite
from config import OCR_CACHE_RETENTION_DAYS, OCR_CACHE_DB_PATH


def compute_image_hash(base64_image: str) -> str:
    """
    Compute SHA256 hash of base64 image data for cache key.
    
    Args:
        base64_image: Base64 encoded image string
        
    Returns:
        Hex string of SHA256 hash
    """
    return hashlib.sha256(base64_image.encode('utf-8')).hexdigest()


async def init_cache_database():
    """Initialize the OCR cache database with required tables."""
    # Ensure parent directory exists
    OCR_CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(OCR_CACHE_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ocr_cache (
                image_hash TEXT PRIMARY KEY,
                ocr_text TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_filename TEXT,
                page_num INTEGER
            )
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON ocr_cache(created_at)
        """)
        
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_accessed ON ocr_cache(last_accessed)
        """)
        
        await db.commit()


async def get_cached_ocr(image_hash: str) -> Optional[Tuple[str, int, int]]:
    """
    Retrieve cached OCR result for given image hash.
    
    Args:
        image_hash: SHA256 hash of the image
        
    Returns:
        Tuple of (ocr_text, input_tokens, output_tokens) if found, None otherwise
    """
    async with aiosqlite.connect(OCR_CACHE_DB_PATH) as db:
        # Update last_accessed timestamp
        await db.execute("""
            UPDATE ocr_cache 
            SET last_accessed = CURRENT_TIMESTAMP 
            WHERE image_hash = ?
        """, (image_hash,))
        
        # Retrieve cached result
        cursor = await db.execute("""
            SELECT ocr_text, input_tokens, output_tokens 
            FROM ocr_cache 
            WHERE image_hash = ?
        """, (image_hash,))
        
        result = await cursor.fetchone()
        await db.commit()
        
        if result:
            return result[0], result[1], result[2]
        return None


async def save_ocr_to_cache(
    image_hash: str, 
    ocr_text: str, 
    input_tokens: int, 
    output_tokens: int,
    pdf_filename: Optional[str] = None,
    page_num: Optional[int] = None
):
    """
    Save OCR result to cache.
    
    Args:
        image_hash: SHA256 hash of the image
        ocr_text: Extracted text from OCR
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens generated
        pdf_filename: Optional filename for debugging
        page_num: Optional page number for debugging
    """
    async with aiosqlite.connect(OCR_CACHE_DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO ocr_cache 
            (image_hash, ocr_text, input_tokens, output_tokens, pdf_filename, page_num)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (image_hash, ocr_text, input_tokens, output_tokens, pdf_filename, page_num))
        
        await db.commit()


async def clean_old_cache_entries():
    """
    Remove cache entries older than OCR_CACHE_RETENTION_DAYS.
    This should be called periodically to manage cache size.
    """
    cutoff_date = datetime.now() - timedelta(days=OCR_CACHE_RETENTION_DAYS)
    
    async with aiosqlite.connect(OCR_CACHE_DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM ocr_cache 
            WHERE created_at < ?
        """, (cutoff_date.isoformat(),))
        
        count_to_delete = (await cursor.fetchone())[0]
        
        if count_to_delete > 0:
            await db.execute("""
                DELETE FROM ocr_cache 
                WHERE created_at < ?
            """, (cutoff_date.isoformat(),))
            
            await db.commit()
            print(f"Cleaned {count_to_delete} old OCR cache entries")
        
        # Also clean up entries that haven't been accessed in a while
        old_access_cutoff = datetime.now() - timedelta(days=OCR_CACHE_RETENTION_DAYS * 2)
        
        cursor = await db.execute("""
            SELECT COUNT(*) FROM ocr_cache 
            WHERE last_accessed < ?
        """, (old_access_cutoff.isoformat(),))
        
        old_access_count = (await cursor.fetchone())[0]
        
        if old_access_count > 0:
            await db.execute("""
                DELETE FROM ocr_cache 
                WHERE last_accessed < ?
            """, (old_access_cutoff.isoformat(),))
            
            await db.commit()
            print(f"Cleaned {old_access_count} unused OCR cache entries")


async def get_cache_stats() -> dict:
    """
    Get statistics about the OCR cache.
    
    Returns:
        Dictionary with cache statistics
    """
    async with aiosqlite.connect(OCR_CACHE_DB_PATH) as db:
        # Total entries
        cursor = await db.execute("SELECT COUNT(*) FROM ocr_cache")
        total_entries = (await cursor.fetchone())[0]
        
        # Entries from last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        cursor = await db.execute("""
            SELECT COUNT(*) FROM ocr_cache 
            WHERE created_at > ?
        """, (yesterday.isoformat(),))
        recent_entries = (await cursor.fetchone())[0]
        
        # Total tokens saved (approximation)
        cursor = await db.execute("""
            SELECT SUM(input_tokens + output_tokens) FROM ocr_cache
        """, )
        total_tokens_saved = (await cursor.fetchone())[0] or 0
        
        # Database size
        db_size_bytes = OCR_CACHE_DB_PATH.stat().st_size if OCR_CACHE_DB_PATH.exists() else 0
        
        return {
            "total_entries": total_entries,
            "recent_entries": recent_entries,
            "total_tokens_saved": total_tokens_saved,
            "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
            "retention_days": OCR_CACHE_RETENTION_DAYS
        }


# Database will be initialized when first accessed
# via init_cache_database() calls in the OCR service functions