"""Configuration settings for PDF Utilities Web Application."""

import os as _os
from pathlib import Path


def _flag(name: str) -> bool:
    return _os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


# ── Local mode ───────────────────────────────────────────────────────────────
# Set by `pdf-web-app --local` (which exports PDF_LOCAL_MODE before this module
# is first imported). Local mode assumes no reverse proxy and no cloud account:
# uploads go straight to the process, and GCS is switched off even if a bucket
# is still configured in .env.
LOCAL_MODE: bool = _flag("PDF_LOCAL_MODE")

# File handling settings
FILE_RETENTION_DAYS = 30
# Cap for the plain multipart POST. In production this is bounded by nginx's
# `client_max_body_size 100m` and Cloudflare's 100 MB proxy limit; locally there
# is no proxy in the way, so the only real constraint is RAM (the upload is read
# into memory before hashing).
MAX_FILE_SIZE_MB = int(_os.getenv("MAX_FILE_SIZE_MB", "500" if LOCAL_MODE else "100"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Directory settings
UPLOAD_DIR = Path("uploads")
DB_PATH = Path("data/pdf_files.db")

# Server settings
SERVER_PORT = 8000

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.epub', '.jpg', '.jpeg', '.png', '.webp', '.ppt', '.pptx', '.md'}

# LibreOffice conversion settings
LIBREOFFICE_TIMEOUT = 60  # seconds to wait for soffice conversion

# Pandoc (Markdown -> PDF via typst) conversion settings
PANDOC_TIMEOUT = 60  # seconds to wait for pandoc conversion
PANDOC_MAIN_FONT = "Noto Sans"
PANDOC_MONO_FONT = "Noto Sans Mono"

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
# Model stubs ("-latest") track Google's newest release in each tier automatically.
OCR_MODEL = "gemini-flash-lite-latest"  # Direct GenAI model
OCR_THINKING_LEVEL = "MINIMAL"  # See HANDWRITING_THINKING_LEVEL for the measurements
OCR_TIMEOUT = 60
OCR_MAX_TOKENS = 4096
# OCR processes one page at a time for simplicity and reliability

# Handwriting OCR (camera capture) settings
# Kept on separate knobs so a regression in one tier cannot degrade the other.
HANDWRITING_OCR_MODEL = "gemini-flash-latest"
# LOW is a floor imposed by the model, not a preference. As of 2026-08-14 the
# `gemini-flash-latest` stub moved to a generation that rejects MINIMAL outright:
#
#   400 INVALID_ARGUMENT: Thinking level MINIMAL is not supported for this model.
#
# That is a hard failure on every /capture transcription, so LOW is the lowest setting
# that runs at all on this tier. Flash-Lite still accepts MINIMAL, which is why
# OCR_THINKING_LEVEL above is unchanged.
#
# We pay real accuracy for this. Measured across 5 handwritten pages (standup notes, hour
# estimates, a question list, a dense demo script, and a page of Ramsey-model calculus),
# 2 runs per cell, scoring recovery of the hard terms and LaTeX structures:
#
#   flash MINIMAL 96.5% (~2.5s, $0.004)   flash LOW  92.2%    flash MEDIUM 80.5% (~20s, $0.031)
#   lite  MINIMAL 92.6% (~1.6s, $0.001)   lite  LOW  88.7%    lite  MEDIUM 89.0%
#
# More thinking made transcription worse, not better, and MEDIUM has a failure mode where
# the model emits its own deliberation ("Let's read: J-a-s-p-r-e-e-t... Wait!") as the
# transcription. Transcription is perception, not reasoning — there is nothing to reason
# about, so the budget gets spent second-guessing correct readings. So: do not raise this
# past LOW, and drop back to MINIMAL if a future stub accepts it again. Those numbers
# predate the current stub — re-measure before trusting them as this model's scores.
HANDWRITING_THINKING_LEVEL = "LOW"
CAPTURE_JPEG_QUALITY = 0.92  # Canvas toBlob quality for camera frames (0.0-1.0)

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

# PDF-from-URL settings (server-side download of a direct .pdf link)
PDF_URL_FETCH_TIMEOUT = 120       # seconds for the whole download
PDF_URL_MAX_REDIRECTS = 5
# Sent because several publishers (SSRN, JSTOR, some journals) return 403 to a
# bare client. Nothing here pretends to be a browser beyond the User-Agent.
PDF_URL_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# URL-to-PDF-OCR settings (browser-based capture)
URL_PDF_BROWSER_TIMEOUT = 30000      # ms: page navigation + network idle timeout
URL_PDF_PRINT_WAIT_MS = 1500         # ms: wait after scroll for popups to appear
URL_PDF_QUALITY_CHECK_ENABLED = True # Run LLM quality check before full OCR
# Optional: path to a Chromium/Chrome binary; leave empty to use playwright default
URL_PDF_CHROMIUM_EXECUTABLE = ""

# Auth settings
LOGIN_PASSWORD: str = _os.getenv("LOGIN_PASSWORD", "")
SESSION_SECRET_KEY: str = _os.getenv("SESSION_SECRET_KEY", "pdf-app-dev-secret-change-me")

# ── GCS: large-file upload bypass ────────────────────────────────────────────
# The browser PUTs the file straight to a signed GCS URL, so the bytes never
# pass through Cloudflare or nginx; the server then pulls it back out of the
# bucket. Only worth the extra round trip for files the proxy would reject,
# hence the threshold below — smaller files stay on the plain multipart path.
GCS_BUCKET_NAME: str = "" if LOCAL_MODE else _os.getenv("GCS_BUCKET_NAME", "")
GCS_CREDENTIALS_FILE: str | None = _os.getenv("GCS_CREDENTIALS_FILE") or None
GCS_SIGNED_URL_EXPIRY_MINUTES: int = int(_os.getenv("GCS_SIGNED_URL_EXPIRY_MINUTES", "15"))
GCS_DELETE_AFTER_DOWNLOAD: bool = _os.getenv("GCS_DELETE_AFTER_DOWNLOAD", "true").lower() == "true"
GCS_ENABLED: bool = bool(GCS_BUCKET_NAME)

# Files above this go via GCS. Must stay under nginx's 100m, or a multipart
# upload could be the one that gets truncated at the proxy. Set well below that
# ceiling on purpose: the cloud route is the one that breaks silently when a
# signed URL, a CORS rule or a service-account key goes stale, so it is better
# exercised by ordinary uploads than reserved for the rare huge file. The cost is
# two transfers instead of one for mid-size documents.
GCS_DIRECT_THRESHOLD_MB = int(_os.getenv("GCS_DIRECT_THRESHOLD_MB", "5"))
GCS_DIRECT_THRESHOLD_BYTES = GCS_DIRECT_THRESHOLD_MB * 1024 * 1024

# Ceiling for the GCS path. Higher than the multipart cap because no proxy sees
# these bytes — but the server still holds the whole file in memory while
# hashing it, so this is not a free number to raise.
MAX_FILE_SIZE_GCS_MB = int(_os.getenv("MAX_FILE_SIZE_GCS_MB", "500"))
MAX_FILE_SIZE_GCS_BYTES = MAX_FILE_SIZE_GCS_MB * 1024 * 1024

# The largest upload this deployment will accept by any route — what the UI
# should advertise.
EFFECTIVE_MAX_UPLOAD_MB = max(MAX_FILE_SIZE_MB,
                              MAX_FILE_SIZE_GCS_MB if GCS_ENABLED else 0)