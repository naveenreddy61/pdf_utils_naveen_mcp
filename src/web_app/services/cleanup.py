"""Background cleanup tasks for old files."""

import asyncio
from datetime import datetime, timedelta
from config import FILE_RETENTION_DAYS, UPLOAD_DIR
from src.web_app.core.database import get_old_files, delete_file_record


async def cleanup_old_files():
    """Remove files older than FILE_RETENTION_DAYS."""
    cutoff_date = datetime.now() - timedelta(days=FILE_RETENTION_DAYS)
    
    # Find old files
    old_files = get_old_files(cutoff_date)
    
    for file_record in old_files:
        # Delete the physical file
        file_path = UPLOAD_DIR / file_record.stored_filename
        if file_path.exists():
            file_path.unlink()
        
        # Delete processed files (with mcp_ prefix)
        # Remove extension from stored filename for pattern matching
        base_name = file_record.stored_filename.rsplit('.', 1)[0]
        for f in UPLOAD_DIR.glob(f"mcp_{base_name}_*"):
            f.unlink()
        
        # Remove from database
        delete_file_record(file_record.file_hash)
    
    return len(old_files)


async def daily_cleanup():
    """Run cleanup daily."""
    while True:
        await asyncio.sleep(86400)  # 24 hours
        try:
            await cleanup_old_files()
        except Exception as e:
            print(f"Error in daily cleanup: {e}")