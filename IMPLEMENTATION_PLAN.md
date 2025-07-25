# PDF Utilities FastHTML Web App Implementation Plan

## Overview
Created a FastHTML web application that exposes PDF processing utilities with file deduplication and automatic cleanup.

## Key Design Decisions

### 1. File Upload Strategy
- **Unified Approach**: Same file upload mechanism for both local development and production
- **Temporary Storage**: All uploaded files stored in `uploads/` directory
- **No Environment Modes**: Simplified codebase without LOCAL vs PRODUCTION distinctions

### 2. File Deduplication System
- **Hash-Based Storage**: SHA-256 hash used to identify duplicate files
- **Database Tracking**: SQLite database stores file metadata:
  - file_hash (primary key)
  - original_filename
  - stored_filename
  - file_size
  - page_count
  - upload_date
  - last_accessed
- **Reuse Existing Files**: When duplicate detected, updates last_accessed time instead of re-uploading

### 3. File Retention Policy
- **30-Day Retention**: Files kept for 30 days (configurable via `FILE_RETENTION_DAYS`)
- **Daily Cleanup**: Background task runs every 24 hours to remove old files
- **Manual Cleanup**: `/cleanup` endpoint for testing/manual trigger

### 4. File Size Limit
- **100MB Maximum**: Configurable via `MAX_FILE_SIZE_MB` constant
- **Validation**: File size checked before processing

## Implementation Details

### Core Components

1. **app.py** - Main FastHTML application with:
   - File upload with drag-and-drop support
   - Hash-based deduplication
   - PDF operations (TOC, page extraction, image conversion, text extraction)
   - Results display and download functionality
   - Background cleanup task

2. **Database Schema**:
   ```python
   files = db.create(
       Dict(
           file_hash=str,        # Primary key
           original_filename=str,
           stored_filename=str,
           file_size=int,
           page_count=int,
           upload_date=str,
           last_accessed=str
       ),
       pk='file_hash'
   )
   ```

3. **File Naming Convention**:
   - Uploaded files: `{hash[:8]}_{sanitized_filename}.pdf`
   - Extracted pages: `mcp_{base}_pages_{start}_to_{end}.pdf`
   - Converted images: `mcp_{base}_page_{num}.{format}`
   - Extracted text: `mcp_{base}_text_p{start}-{end}.{txt|md}`

### Routes

- `/` - Home page with upload form
- `/upload` - Handle file upload with deduplication
- `/process/toc/{file_hash}` - Extract table of contents
- `/extract-pages-form/{file_hash}` - Show page extraction form
- `/process/extract-pages/{file_hash}` - Extract pages
- `/convert-images-form/{file_hash}` - Show image conversion form
- `/process/convert-images/{file_hash}` - Convert to images
- `/extract-text-form/{file_hash}` - Show text extraction form
- `/process/extract-text/{file_hash}` - Extract text
- `/download/{filename}` - Download processed files
- `/cleanup` - Manual cleanup trigger

### Security Features

1. **File Validation**:
   - Only PDF files accepted
   - File size limit enforced
   - Filename sanitization

2. **Path Security**:
   - All file operations within UPLOAD_DIR
   - No user-provided paths accepted

3. **Hash-Based References**:
   - Files referenced by hash, not user-provided names
   - Prevents directory traversal attacks

## Usage

### Running the Application

```bash
# Install dependencies
uv sync

# Run the application
uv run app.py
```

The app will be available at `http://localhost:8000`

### Deployment Considerations

1. **Persistent Storage**: Ensure `uploads/` directory is persistent across deployments
2. **Database Backup**: Regular backups of `pdf_files.db`
3. **Disk Space**: Monitor available space for file storage
4. **Cleanup Schedule**: Adjust `FILE_RETENTION_DAYS` based on usage patterns
5. **Authentication**: Add authentication for production deployment (especially for `/cleanup`)

## Future Enhancements

1. **User Accounts**: Track uploads per user
2. **Batch Operations**: Process multiple files at once
3. **OCR Support**: Add text extraction from scanned PDFs
4. **Preview**: Show PDF preview before processing
5. **Progress Bars**: Real-time progress for long operations
6. **API Endpoints**: RESTful API for programmatic access