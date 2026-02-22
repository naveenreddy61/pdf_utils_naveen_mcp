"""Configuration settings for PDF Utilities Web Application."""

from pathlib import Path

# File handling settings
FILE_RETENTION_DAYS = 30
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Directory settings
UPLOAD_DIR = Path("uploads")
DB_PATH = Path("data/pdf_files.db")

# Server settings
SERVER_PORT = 8000

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}

# Image conversion settings
DEFAULT_DPI = 150
MAX_DPI = 300
MIN_DPI = 72

# Token counting model
TOKEN_COUNTING_MODEL = "gpt-4o"

# Image extraction settings
IMAGE_COMPRESSION_QUALITY = 85  # JPEG compression quality (1-100)
MIN_IMAGE_SIZE = 25  # Minimum width/height in pixels
MAX_IMAGES_PER_PAGE = 12  # Maximum images to extract per page
IMAGE_PREVIEW_SIZE = 300  # Thumbnail display size in pixels

# OCR with LLM settings
OCR_MODEL = "gemini-2.5-flash-lite"  # Direct GenAI model
OCR_TEMPERATURE = 0.1
OCR_TIMEOUT = 60
OCR_MAX_TOKENS = 4096
# OCR processes one page at a time for simplicity and reliability

# Async OCR settings
OCR_CONCURRENT_REQUESTS = 20  # Max concurrent LLM requests
OCR_MAX_RETRIES = 3  # Max retry attempts per page
OCR_RETRY_DELAY_BASE = 1.0  # Base delay for exponential backoff (seconds)
OCR_BATCH_TIMEOUT = 300  # Overall timeout for batch processing (seconds)

# OCR Caching settings
OCR_CACHE_RETENTION_DAYS = 14  # Keep cached OCR results for 2 weeks
OCR_CACHE_DB_PATH = Path("data/ocr_cache.db")  # SQLite DB for caching

# ── Google Cloud Storage (direct browser upload bypass) ──────────────────────
# Set these to enable GCS-backed uploads that bypass Cloudflare's 100 MB limit.
# Leave GCS_BUCKET_NAME empty / unset to fall back to local multipart upload.
import os as _os
GCS_BUCKET_NAME: str = _os.getenv("GCS_BUCKET_NAME", "")
# Path to a service-account JSON key file.  Leave blank to use ADC /
# GOOGLE_APPLICATION_CREDENTIALS environment variable.
GCS_CREDENTIALS_FILE: str | None = _os.getenv("GCS_CREDENTIALS_FILE") or None
# How long the signed upload URL stays valid (browser must start uploading within this window).
GCS_SIGNED_URL_EXPIRY_MINUTES: int = int(_os.getenv("GCS_SIGNED_URL_EXPIRY_MINUTES", "15"))
# Delete temp GCS object after the server has pulled it down locally.
GCS_DELETE_AFTER_DOWNLOAD: bool = _os.getenv("GCS_DELETE_AFTER_DOWNLOAD", "true").lower() == "true"