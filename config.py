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
ALLOWED_EXTENSIONS = {'.pdf'}

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
OCR_PAGES_PER_CHUNK = 2  # Number of pages to process per API call

# Async OCR settings
OCR_CONCURRENT_REQUESTS = 20  # Max concurrent LLM requests
OCR_MAX_RETRIES = 3  # Max retry attempts per page
OCR_RETRY_DELAY_BASE = 1.0  # Base delay for exponential backoff (seconds)
OCR_BATCH_TIMEOUT = 300  # Overall timeout for batch processing (seconds)

# OCR Caching settings
OCR_CACHE_RETENTION_DAYS = 14  # Keep cached OCR results for 2 weeks
OCR_CACHE_DB_PATH = Path("data/ocr_cache.db")  # SQLite DB for caching