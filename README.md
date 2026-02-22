# PDF & Image Processing Web Application

A powerful, browser-based application for processing PDF documents and images with AI-powered OCR. Built with FastHTML and powered by PyMuPDF and Google Gemini, this tool provides an intuitive interface for common PDF operations.

## Features

### Core PDF Operations
- **Table of Contents Extraction**: View complete TOC/bookmarks from PDF files in a hierarchical display
- **Page Range Extraction**: Extract specific page ranges into new PDF files
- **Page to Image Conversion**: Convert PDF pages to high-quality PNG or JPEG images (72-300 DPI)
- **Text Extraction**: Extract text from PDF pages with optional Markdown formatting
- **AI-Powered OCR**: Extract text from scanned PDFs and images using Google Gemini 2.5 Flash Lite

### Image Processing
- **Multi-Format Support**: Upload and process JPG, PNG, WEBP images
- **Smart Image Extraction**: Automatically extract and filter images from PDFs
- **Image OCR**: Perform OCR on standalone image files
- **Batch Processing**: Process multiple pages or images efficiently

### User Experience
- **Drag-and-Drop Upload**: Easy file uploading with automatic processing
- **Interactive UI**: Clean, responsive interface with real-time feedback
- **Copy to Clipboard**: One-click copying for extracted text
- **Download Results**: Download processed PDFs, images, and text files
- **File Deduplication**: Automatic detection and reuse of previously uploaded files
- **Auto-Cleanup**: 30-day retention policy with automatic file cleanup
- **Progress Indicators**: Real-time feedback during processing

### Advanced Features
- **Async OCR Processing**: Fast, concurrent API requests with rate limiting
- **Intelligent Caching**: SQLite-based cache reduces API costs by ~24%
- **Deterministic Cache Keys**: Stable caching based on file metadata
- **Token Tracking**: Monitor API usage and costs
- **Error Resilience**: Automatic fallback to PyMuPDF extraction

## Quick Start (No Installation!)

Run the web application instantly without installing anything:

```bash
# Basic usage (PDF operations work without API key)
uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app

# With OCR support (requires Gemini API key)
export GOOGLE_API_KEY='your-key-here'
uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app

# Or in one line
GOOGLE_API_KEY='your-key' uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app

# Custom port
uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app --port 9000

# Custom host (default: 0.0.0.0)
uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app --host 127.0.0.1
```

Then open http://localhost:8000 in your browser!

**Note**: Basic PDF operations (TOC, page extraction, image conversion) work without an API key. Only OCR requires it.

## Getting a Gemini API Key

OCR features require a free Google Gemini API key:

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Create or select a project
4. Click "Create API Key"
5. Copy the API key

**Setting the API Key:**

```bash
# For current session
export GOOGLE_API_KEY='your-key-here'

# For persistent setup (add to ~/.bashrc or ~/.zshrc)
echo 'export GOOGLE_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

**Alternative environment variable:**
```bash
export GEMINI_API_KEY='your-key-here'  # Also supported
```

## Installation

### Prerequisites

- **Python 3.12+**: Required for running the application
- **uv**: Recommended for dependency management

Install uv:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

### Option 1: Quick Install (Recommended)

Install directly from GitHub:

```bash
pip install git+https://github.com/naveenreddy61/anki_nav_mcp_server.git
```

Then run:
```bash
pdf-web-app
```

### Option 2: Development Setup

Clone and run locally:

```bash
# Clone the repository
git clone https://github.com/naveenreddy61/anki_nav_mcp_server.git
cd anki_nav_mcp_server

# Install dependencies
uv sync

# Run the application
uv run app.py
```

### Option 3: uvx (No Installation)

Run directly without installation (see Quick Start above).

## Usage

### Starting the Application

**After installation:**
```bash
pdf-web-app
```

**From local clone:**
```bash
uv run app.py
```

**With uvx:**
```bash
uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app
```

The application will start on http://localhost:8000 (or your specified port).

### Web Interface Guide

#### 1. Upload Files

- Click "Choose File" or drag and drop a file
- Supported formats: PDF, JPG, JPEG, PNG, WEBP
- Maximum file size: 100MB
- Files are retained for 30 days

#### 2. Extract Table of Contents

**For PDFs with bookmarks:**
- Click "Extract Table of Contents" button
- View hierarchical TOC with page numbers
- Displays nested structure with indentation

**Use cases:**
- Navigate large documents
- Understand document structure
- Find specific sections quickly

#### 3. Extract Pages

**Create a new PDF from selected pages:**
- Click "Extract Pages" button
- Enter start page number (e.g., 5)
- Enter end page number (e.g., 10)
- Click "Extract" to create new PDF
- Download the extracted file

**Use cases:**
- Share specific chapters
- Split large documents
- Extract relevant sections

#### 4. Convert to Images

**Convert PDF pages to image files:**
- Click "Convert to Images" button
- Enter start and end page numbers
- Select DPI (resolution):
  - 72 DPI: Screen viewing
  - 150 DPI: General use (default)
  - 300 DPI: High quality printing
- Choose format: PNG or JPG
- View thumbnails and download individual images or all as ZIP

**Use cases:**
- Extract diagrams and charts
- Create presentation slides
- Share visual content
- Archive important pages

#### 5. Extract Text (with OCR)

**Extract text from PDFs and images:**
- Click "Extract Text" button
- Enter page range (for PDFs)
- Text is extracted using AI-powered OCR
- Preview the full text in the browser
- Copy to clipboard with one click
- Download as .txt file
- View token usage statistics

**Use cases:**
- Convert scanned documents to searchable text
- Extract text from images
- Copy content for reuse
- Archive document content

**OCR Features:**
- Processes one page at a time for reliability
- Concurrent processing for speed (20 pages at once)
- Intelligent caching reduces API costs
- Token tracking for cost monitoring
- Automatic retry on failures

### Example Workflows

**Workflow 1: Extract Chapter from Book**
1. Upload PDF book
2. Extract TOC to find chapter location
3. Note chapter start/end pages
4. Extract pages as new PDF
5. Download chapter PDF

**Workflow 2: Digitize Scanned Documents**
1. Upload scanned PDF or image
2. Use Extract Text with OCR
3. Review extracted text
4. Copy to clipboard or download
5. Edit in your preferred text editor

**Workflow 3: Create Presentation from PDF**
1. Upload source PDF
2. Convert specific pages to images (300 DPI, PNG)
3. Download images
4. Insert into presentation software

**Workflow 4: Archive Important Documents**
1. Upload PDF document
2. Extract text for searchability
3. Convert key pages to images
4. Store both text and images

## Configuration

### Application Settings

Located in `src/pdf_utils/config.py`:

#### File Handling
```python
FILE_RETENTION_DAYS = 30      # Auto-cleanup period
MAX_FILE_SIZE_MB = 100         # Maximum upload size
UPLOAD_DIR = Path("uploads")   # Storage directory
```

#### Image Processing
```python
DEFAULT_DPI = 150              # Default image resolution
MIN_DPI = 72                   # Minimum DPI
MAX_DPI = 300                  # Maximum DPI
IMAGE_COMPRESSION_QUALITY = 85 # JPEG quality (1-100)
MIN_IMAGE_SIZE = 25            # Min width/height in pixels
MAX_IMAGES_PER_PAGE = 12       # Max images extracted per page
```

#### OCR Settings
```python
OCR_MODEL = "gemini-2.5-flash-lite"
OCR_TEMPERATURE = 0.1          # Low for consistent output
OCR_TIMEOUT = 60               # Per-page timeout (seconds)
OCR_MAX_TOKENS = 4096          # Per-page token limit
OCR_CONCURRENT_REQUESTS = 20   # Parallel API requests
OCR_MAX_RETRIES = 3            # Retry failed pages
```

#### Cache Settings
```python
OCR_CACHE_RETENTION_DAYS = 14  # Cache cleanup period
OCR_CACHE_DB_PATH = Path("data/ocr_cache.db")
```

### Environment Variables

```bash
# Required for OCR
GOOGLE_API_KEY=your_key_here
# or
GEMINI_API_KEY=your_key_here

# Optional server configuration
SERVER_PORT=8000  # Override default port
```

### CLI Options

```bash
pdf-web-app --help

Options:
  -p, --port PORT         Port to run server on (default: 8000)
  --host HOST            Host to bind to (default: 0.0.0.0)
  --no-api-key-check     Skip API key validation (for testing)
  -h, --help             Show help message
```

## Performance & Costs

### OCR Processing Speed

- **With cache hit**: ~0.01s per page
- **Without cache (first time)**: ~3-6s per page
- **Concurrent processing**: 20 pages processed simultaneously
- **Typical 10-page document**: 4-5 seconds (first run), <1 second (cached)

### API Costs (Google Gemini 2.5 Flash Lite)

**Pricing** (as of 2025):
- Input: $0.00001875/1K tokens
- Output: $0.000075/1K tokens

**Typical Usage:**
- Single page PDF: ~1,000-2,000 input tokens, ~500-1,000 output tokens
- Cost per page: ~$0.0001-0.0003 (less than $0.0003 per page)
- 100 pages: ~$0.01-0.03

**With Caching:**
- Repeated documents: ~$0 (served from cache)
- Typical savings: 24% token reduction
- Cache hit rate: ~100% for repeated documents

### Storage

- **Uploaded files**: ~same as original file size
- **Extracted PDFs**: ~proportional to extracted pages
- **Images**: ~500KB-2MB per page (depends on DPI)
- **OCR cache**: ~1KB per cached page
- **Auto-cleanup**: Files older than 30 days removed

## Troubleshooting

### Installation Issues

**Problem**: `uvx` command not found
**Solution**:
```bash
# Install uv first
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

**Problem**: Python version too old
**Solution**: Install Python 3.12 or later
```bash
# Check version
python --version

# Download from https://www.python.org/downloads/
```

### Application Issues

**Problem**: Port 8000 already in use
**Solution**:
```bash
# Use a different port
pdf-web-app --port 9000
```

**Problem**: Upload fails with "File too large"
**Solution**:
- File must be under 100MB
- Or modify `MAX_FILE_SIZE_MB` in config.py

**Problem**: "No API key found" warning
**Solution**:
```bash
# Set environment variable
export GOOGLE_API_KEY='your-key-here'

# Or use --no-api-key-check for testing (OCR won't work)
pdf-web-app --no-api-key-check
```

### OCR Issues

**Problem**: OCR extraction fails or returns errors
**Solutions**:
- Verify API key is valid
- Check internet connection
- Ensure API quota not exceeded
- Check error message for specific issue

**Problem**: OCR is slow
**Solutions**:
- First run is slower (no cache)
- Subsequent runs use cache (~100x faster)
- Reduce concurrent requests in config if hitting rate limits
- Use lower DPI for faster image processing

**Problem**: High API costs
**Solutions**:
- Cache is automatically used (check cache hit rate in logs)
- Increase cache retention days
- Process only necessary pages
- Use PyMuPDF fallback for searchable PDFs (no API call)

### File Processing Issues

**Problem**: "Failed to extract TOC"
**Cause**: PDF has no embedded bookmarks
**Solution**: Not all PDFs have TOC - this is normal

**Problem**: Downloaded files show 404 error
**Solutions**:
- Ensure `uploads/` directory exists
- Check file permissions
- Verify files weren't auto-cleaned (>30 days old)

**Problem**: Images appear blurry
**Solution**: Increase DPI (try 300 for high quality)

**Problem**: "Copy to Clipboard" fails
**Solutions**:
- Use HTTPS or localhost (security requirement)
- Try a modern browser (Chrome, Firefox, Edge, Safari)
- Check browser permissions for clipboard access

### Database Issues

**Problem**: Database errors on startup
**Solutions**:
```bash
# Remove and recreate databases
rm -f data/pdf_files.db data/ocr_cache.db
# Restart application (databases recreate automatically)
```

**Problem**: Disk space full
**Solutions**:
- Clean old uploads manually: `rm -rf uploads/*`
- Reduce retention days in config
- Clean cache: `rm -f data/ocr_cache.db`

## Development

### Project Structure

```
pdf-utils-web/
├── src/
│   ├── pdf_utils/              # Shared configuration
│   │   ├── __init__.py
│   │   └── config.py
│   └── web_app/                # Web application
│       ├── cli.py              # CLI entry point
│       ├── app.py              # FastHTML app
│       ├── core/               # Core utilities
│       │   ├── database.py     # File tracking
│       │   └── utils.py        # Helper functions
│       ├── services/           # Business logic
│       │   ├── pdf_service.py  # PDF operations
│       │   ├── ocr_service.py  # OCR processing
│       │   ├── ocr_cache.py    # Cache management
│       │   └── cleanup.py      # File cleanup
│       ├── routes/             # HTTP routes
│       │   ├── main.py         # Upload and home
│       │   ├── pdf.py          # PDF operations
│       │   └── api.py          # API endpoints
│       ├── ui/                 # UI components
│       │   ├── components.py   # Reusable elements
│       │   └── styles.py       # CSS styles
│       └── prompts/            # LLM prompts
│           ├── ocr_prompt.txt
│           ├── ocr_prompt_pdf.txt
│           └── math_detection_prompt.txt
├── data/                       # Runtime data
│   ├── pdf_files.db           # File metadata
│   └── ocr_cache.db           # OCR results cache
├── uploads/                    # Uploaded files
├── tests/                      # Test suite
├── app.py                      # Local dev entry point
├── pyproject.toml              # Project configuration
├── README.md                   # This file
└── CLAUDE.md                   # Development guide
```

### Development Commands

```bash
# Install dependencies
uv sync

# Run web application
uv run app.py

# Or use the CLI entry point
uv run python -m web_app.cli

# Run tests
uv run python tests/test_ocr_service.py

# Add a dependency
uv add package_name

# Build distribution
uv build

# Inspect wheel contents
unzip -l dist/*.whl
```

### Adding New Features

#### Add a New PDF Operation

1. **Implement in `pdf_service.py`**:
```python
def new_operation(pdf_path: Path, param: str) -> Result:
    """New PDF operation."""
    doc = pymupdf.open(pdf_path)
    # ... implementation
    doc.close()
    return result
```

2. **Add route in `routes/pdf.py`**:
```python
@rt('/process/new-operation/{file_hash}')
def process_new_operation(file_hash: str):
    # Handle form, call service, return result
    pass
```

3. **Add button in `ui/components.py`**:
```python
def operation_buttons():
    return Div(
        # ... existing buttons
        Button("New Operation", hx_get=f"/new-operation-form/{file_hash}")
    )
```

4. **Test the feature** via browser

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function parameters and returns
- Add docstrings for all public functions
- Keep functions focused and single-purpose
- Use async/await for I/O-bound operations

### Testing

```bash
# Test OCR service
uv run python tests/test_ocr_service.py

# Test with sample PDFs
uv run python create_test_pdf.py

# Manual testing
uv run app.py
# Upload files via http://localhost:8000
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Ensure code follows the style guide
6. Update documentation
7. Submit a pull request

### Pull Request Guidelines

- Provide clear description of changes
- Include screenshots for UI changes
- Update README if adding features
- Test thoroughly before submitting
- Keep PRs focused on single feature/fix

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [FastHTML](https://github.com/AnswerDotAI/fasthtml) - Modern Python web framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) - Powerful PDF processing library
- [PyMuPDF4LLM](https://github.com/pymupdf/PyMuPDF4LLM) - PDF to Markdown conversion
- [Google Gemini](https://ai.google.dev/) - AI-powered OCR
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review existing GitHub issues
3. Create a new issue with:
   - Detailed problem description
   - Steps to reproduce
   - Environment information (OS, Python version)
   - Error messages or logs

---

## GCS Setup – Large File Upload Bypass

By default every upload travels through Cloudflare, which enforces a **100 MB limit** on proxied requests. The GCS integration lets the browser upload directly to Google Cloud Storage via a short-lived signed URL, so Cloudflare never sees the file bytes.

### What you need from GCP

| Item | Where to create it |
|------|--------------------|
| GCP Project | Already exists if you have credits |
| Cloud Storage bucket | Cloud Console → Storage → Create bucket |
| Service Account | IAM & Admin → Service Accounts → Create |
| SA key JSON | Service Account → Keys → Add Key → JSON |

**Minimum IAM role** on the bucket: `roles/storage.objectAdmin` (or a custom role with `storage.objects.create`, `storage.objects.delete`, `storage.objects.get`).

### CORS configuration (required)

The browser PUTs directly to GCS, so GCS must allow cross-origin requests from your domain. Save this as `cors.json` and apply it once:

```json
[
  {
    "origin": ["https://pdf.naveenreddy61.dev"],
    "method": ["PUT"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
```

```bash
gcloud storage buckets update gs://YOUR_BUCKET_NAME --cors-file=cors.json
```

### Environment variables

Copy `.env.example` to `.env` and fill in:

```
GCS_BUCKET_NAME=your-bucket-name
GCS_CREDENTIALS_FILE=/absolute/path/to/service-account-key.json
GCS_SIGNED_URL_EXPIRY_MINUTES=15   # how long browser has to start the PUT
GCS_DELETE_AFTER_DOWNLOAD=true     # clean up temp GCS objects after download
```

Restart `uv run app.py`. The upload form will automatically switch to the GCS direct-upload path and display a progress bar. If `GCS_BUCKET_NAME` is left empty the app falls back to the original multipart upload.

### Upload flow

```
Browser → /api/request-upload → signed GCS PUT URL
Browser → GCS (direct PUT, bypasses Cloudflare)
Browser → /api/confirm-upload → server pulls file from GCS → local uploads/ → deletes GCS temp object
```

The service account key (`GCS_CREDENTIALS_FILE`) must be on disk — it is used at runtime to sign URLs. Keep it out of version control (it is already in `.gitignore`).

---

**Note**: This server is designed to work with absolute file paths for security and reliability. Always provide full paths when working with PDF files.

---

**Made with FastHTML and PyMuPDF** | **Powered by Google Gemini**
