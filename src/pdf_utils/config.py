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
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.ppt', '.pptx'}

# LibreOffice conversion settings
LIBREOFFICE_TIMEOUT = 60  # seconds to wait for soffice conversion

# Image conversion settings
DEFAULT_DPI = 150
MAX_DPI = 300
MIN_DPI = 72

# Token counting model
TOKEN_COUNTING_MODEL = "gpt-4o"

# Image extraction settings
IMAGE_COMPRESSION_QUALITY = 85  # JPEG compression quality (1-100)
MIN_IMAGE_SIZE = 25  # Minimum width/height in pixels
MAX_IMAGES_PER_PAGE = 25  # Maximum images to extract per page
IMAGE_PREVIEW_SIZE = 300  # Thumbnail display size in pixels

# OCR with LLM settings
OCR_MODEL = "gemini-3.1-flash-lite-preview"  # Direct GenAI model
OCR_TEMPERATURE = 0.1
OCR_TIMEOUT = 60
OCR_MAX_TOKENS = 4096
# OCR processes one page at a time for simplicity and reliability

# Async OCR settings
OCR_CONCURRENT_REQUESTS = 50  # Max concurrent LLM requests
OCR_MAX_RETRIES = 3  # Max retry attempts per page
OCR_RETRY_DELAY_BASE = 1.0  # Base delay for exponential backoff (seconds)
OCR_BATCH_TIMEOUT = 300  # Overall timeout for batch processing (seconds)

# OCR Caching settings
OCR_CACHE_RETENTION_DAYS = 60  # Keep cached OCR results for 2 months
OCR_CACHE_DB_PATH = Path("data/ocr_cache.db")  # SQLite DB for caching

# URL-to-Markdown settings
URL_FETCH_TIMEOUT = 30   # seconds
URL_MAX_CONTENT_LENGTH_MB = 10  # skip pages larger than this

# URL-to-PDF-OCR settings (browser-based capture)
URL_PDF_BROWSER_TIMEOUT = 30000      # ms: page navigation + network idle timeout
URL_PDF_PRINT_WAIT_MS = 1500         # ms: wait after scroll for popups to appear
URL_PDF_QUALITY_CHECK_ENABLED = True # Run LLM quality check before full OCR
# Optional: path to a Chromium/Chrome binary; leave empty to use playwright default
URL_PDF_CHROMIUM_EXECUTABLE = ""

# GCS settings for large file upload bypass
import os as _os
GCS_BUCKET_NAME: str = _os.getenv("GCS_BUCKET_NAME", "")
GCS_CREDENTIALS_FILE: str | None = _os.getenv("GCS_CREDENTIALS_FILE") or None
GCS_SIGNED_URL_EXPIRY_MINUTES: int = int(_os.getenv("GCS_SIGNED_URL_EXPIRY_MINUTES", "15"))
GCS_DELETE_AFTER_DOWNLOAD: bool = _os.getenv("GCS_DELETE_AFTER_DOWNLOAD", "true").lower() == "true"

# ─────────────────────────────────────────────────────────────────────────────
# Modal OCR backend (serverless GPU)
# ─────────────────────────────────────────────────────────────────────────────
# Deploy-time config for the Modal-hosted OCR endpoint. Swapping model or GPU
# means changing these values and re-running `modal deploy modal_app/ocr_app.py`.
# The web app picks between Gemini and Modal via a UI radio per request.

OCR_MODAL_APP_NAME: str = _os.getenv("OCR_MODAL_APP_NAME", "pdf-ocr-modal")
OCR_MODAL_MODEL_ID: str = _os.getenv("OCR_MODAL_MODEL_ID", "deepseek-ai/DeepSeek-OCR-2")
OCR_MODAL_GPU: str = _os.getenv("OCR_MODAL_GPU", "L40S")
OCR_MODAL_ENDPOINT: str = _os.getenv("OCR_MODAL_ENDPOINT", "")
OCR_MODAL_TOKEN_ID: str = _os.getenv("OCR_MODAL_TOKEN_ID", "")
OCR_MODAL_TOKEN_SECRET: str = _os.getenv("OCR_MODAL_TOKEN_SECRET", "")
OCR_MODAL_DPI: int = int(_os.getenv("OCR_MODAL_DPI", "150"))
OCR_MODAL_TIMEOUT: int = int(_os.getenv("OCR_MODAL_TIMEOUT", "180"))
OCR_MODAL_CONCURRENT_REQUESTS: int = int(_os.getenv("OCR_MODAL_CONCURRENT_REQUESTS", "5"))