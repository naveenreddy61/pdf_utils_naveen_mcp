# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PDF MCP (Model Context Protocol) server that enables LLMs to interact with PDF documents using the PyMuPDF library. The server provides tools for extracting information and manipulating PDF files programmatically.

## Architecture

- **FastMCP Framework**: Uses FastMCP for MCP protocol implementation with STDIO transport.
- **PyMuPDF Integration**: Uses the PyMuPDF library for all PDF-related operations.

### Core Components:
- `src/pdf_mcp_server/tools.py`: Contains the business logic for PDF operations (e.g., `PdfTools` class).
- `src/pdf_mcp_server/server.py`: Handles the FastMCP server setup, tool registration, and execution logic.
- `src/pdf_mcp_server/__init__.py`: Serves as the package entry point.

## Web Application Architecture

The project includes a FastHTML web application (`src/web_app/`) for browser-based PDF operations:

### Key Components:
- **Routes**: `src/web_app/routes/` - HTTP endpoints for operations
  - `main.py`: File upload and main page
  - `pdf.py`: PDF processing operations (TOC, text, images, etc.)
  - `api.py`: API endpoints
- **UI Components**: `src/web_app/ui/components.py` - Reusable UI elements
- **Services**: `src/web_app/services/pdf_service.py` - Core PDF operations
- **Styles**: `src/web_app/ui/styles.py` - CSS styles

### Running the Web App:
```bash
uv run app.py  # Starts server on port 8000
```

### VPS Service Management:
For managing the systemd service, nginx, and logs on the VPS, refer to `vps-guide.md`.
Key commands:
- Restart app: `systemctl restart pdf-app`
- View live logs: `journalctl -u pdf-app -f`
- App runs at: https://pdf.naveenreddy61.dev (port 8000, service: `pdf-app`)

### Important Patterns:
- Use HTMX for page updates (`hx_post`, `hx_get`, `hx_target`)
- Use JavaScript `window.location.href` for file downloads (NOT HTMX)
- Images are served from `uploads/` directory
- In-memory processing preferred for performance

## Prerequisites

- **Python 3.12+**: Required for the server.
- **uv**: Recommended for environment and package management.

## Environment Configuration

### Required API Keys:
The OCR service requires Google Gemini API access:

```bash
# .env file (create in project root)
GOOGLE_API_KEY=your_gemini_api_key_here
# Note: GEMINI_API_KEY also supported but GOOGLE_API_KEY takes precedence
```

### Environment Validation:
```bash
# Check Google GenAI client setup
uv run python -c "from google import genai; print('✅ Google GenAI configured')"

# Verify OCR service functionality
uv run python tests/test_ocr_service.py

# Check if API key is detected
uv run python -c "import os; print('✅ API key found' if os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') else '❌ No API key found')"
```

### API Key Setup:
1. Get API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Add to `.env` file in project root
3. Restart any running processes to pick up new environment

## Development Commands

- **Run server locally**: `uv run pdf-mcp-server`
- **Install dependencies**: `uv sync`

## Development Workflow

### Running the Application:
```bash
uv run app.py           # Start web server
uv run main.py          # Run CLI version
uv run pdf-mcp-server   # Start MCP server
```

### Adding Dependencies:
```bash
uv add [package_name]   # Add new dependency (NOT manual pyproject.toml edit)
```

### Testing Changes:
1. Start server: `uv run app.py`
2. Open browser: http://localhost:8000
3. Upload test PDF and verify operations

### Testing Package Distribution:
```bash
# Build wheel
uv build

# Inspect contents
unzip -l dist/*.whl | grep -E "(web_app|pdf_mcp_server|pdf_utils)"

# Should include all three packages:
# - pdf_mcp_server/
# - web_app/ (including prompts/)
# - pdf_utils/

# Test installation in clean environment
uv pip install dist/*.whl
pdf-web-app --help
pdf-mcp-server
```

### Testing with uvx:
```bash
# From local repo
uvx --from . pdf-web-app

# From GitHub (after pushing)
uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app

# With environment variable
GOOGLE_API_KEY=test uvx --from git+https://github.com/naveenreddy61/anki_nav_mcp_server pdf-web-app
```

### Git Workflow:
- `acp` = add, commit, push (as noted in user's global CLAUDE.md)

## OCR Service Architecture (Google GenAI Integration)

The OCR service has been migrated from LiteLLM to Google GenAI for native PDF processing with enhanced performance and reliability.

### Core Components:
- **Google GenAI Client**: Direct PDF processing with `gemini-2.5-flash-lite` model
- **PDF Chunking**: Configurable page grouping (default: 2 pages per API call)
- **Stable Caching**: File-based cache keys for deterministic performance
- **Async Batch Processing**: Semaphore-controlled concurrent requests

### Key Configuration:
```python
# config.py
OCR_MODEL = "gemini-2.5-flash-lite"  # Direct GenAI model (no litellm prefix)
# OCR processes one page at a time for simplicity and reliability
OCR_CONCURRENT_REQUESTS = 20         # Rate limiting for API calls
OCR_TEMPERATURE = 0.1                # Low temperature for consistent OCR
OCR_MAX_TOKENS = 4096               # Per-page token limit
```

### Processing Flow:
1. **Single Page Processing**: Process one page at a time for reliability and simplicity
2. **PDF Subset Creation**: Create in-memory PDF subsets using PyMuPDF's `insert_pdf()`
3. **Native PDF Processing**: Send PDF bytes directly to GenAI API (no image conversion)
4. **Stable Caching**: Cache results using `filename:size:mtime:pages` hash for determinism
5. **Error Resilience**: Fallback to PyMuPDF extraction on any error

### Caching System:
- **Cache Key**: `create_cache_key(pdf_path, page_nums)` for deterministic keys
- **Database**: SQLite in `data/ocr_cache.db`
- **Retention**: 14 days auto-cleanup via `clean_old_cache_entries()`
- **Performance**: ~100% hit rate for repeated documents (vs 0% with non-deterministic keys)
- **Token Savings**: Typical 24% efficiency through cache hits

### API Integration:
```python
# Uses Google GenAI Python SDK
from google import genai
from google.genai import types

client = genai.Client()  # Auto-configured from GOOGLE_API_KEY

# Send PDF directly as inline data
pdf_part = types.Part(
    inline_data=types.Blob(mime_type='application/pdf', data=pdf_bytes)
)

# Token tracking from response
usage = response.usage_metadata
input_tokens = usage.prompt_token_count if usage else 0
output_tokens = usage.candidates_token_count if usage else 0
```

## Async Development Patterns

### CPU-Bound Operations (Token Counting, Heavy Processing)
For CPU-bound synchronous operations that would block the event loop:
- **Pattern**: Use `asyncio.to_thread()` to run blocking operations in thread pool
- **Example**: Token counting with tiktoken (`src/web_app/core/utils.py:31`)
  ```python
  async def count_tokens(text: str) -> int:
      """Non-blocking token counting."""
      return await asyncio.to_thread(_count_tokens_sync, text)
  ```
- **Benefits**: Prevents blocking other concurrent requests (downloads, uploads, etc.)
- **Use cases**: tiktoken encoding, heavy CPU processing, synchronous library calls

### Testing Framework

#### Test Organization:
```
tests/
├── test_ocr_service.py      # Comprehensive OCR testing suite
├── test_pdfs/               # Generated test PDF files
│   ├── test_searchable.pdf
│   ├── test_image_based.pdf
│   └── test_multipage.pdf
└── __init__.py
```

#### Running Tests:
```bash
# Full OCR service test suite (recommended)
uv run python tests/test_ocr_service.py

# Test includes 5 comprehensive scenarios:
# 1. Searchable PDF processing (first run)
# 2. Image-based PDF OCR extraction 
# 3. Cache validation (searchable PDF repeat)
# 4. Cache validation (image-based PDF repeat)
# 5. Multi-page chunking test (3 pages)
```

#### Test Features:
- **PDF Generation**: Creates searchable + image-based test files automatically
- **Cache Testing**: Validates deterministic cache keys and 100% hit rate
- **Token Tracking**: Monitors input/output/saved tokens with detailed reporting
- **Performance**: Speed comparison (cached: 0.01s vs fresh: 3-6s)
- **Chunking**: Tests configurable page grouping (2-page chunks by default)

#### Expected Results:
- **Cache Hit Rate**: 100% for repeated documents  
- **Token Efficiency**: ~24% savings through caching
- **Processing Speed**: >100x faster for cached content
- **Text Quality**: Consistent extraction from both searchable and image PDFs

### Performance Monitoring
Key metrics to watch:
- Cache hit rate (target: >50% for repeated documents)  
- Processing time (target: <3s for 3-page documents)
- Token usage (significantly reduced with caching)
- Retry counts (should be minimal in stable operation)

## Enhanced Development Commands

### Async Testing Workflow
```bash
# Development cycle for async features
uv add [package]                    # Add dependencies
uv run app.py &                     # Start in background  
# Test via browser, then:
kill %1                             # Stop background process
# OR: use process management
ps aux | grep "uv run app.py" | awk '{print $2}' | xargs kill
```

### Performance Testing
```bash
# Create test documents of various sizes
uv run python create_test_pdf.py   # 3-page test
# Upload via web interface and monitor:
# - Processing time logs
# - Cache hit/miss patterns  
# - Retry frequency
```

### Database Operations
```bash
# Initialize cache database
uv run python -c "import asyncio; from src.web_app.services.ocr_cache import init_cache_database; asyncio.run(init_cache_database())"

# Clear cache for testing
rm -f data/ocr_cache.db
```

## Git Workflow

### Feature Development
```bash
git checkout -b feat_[feature_name]  # Create feature branch
# ... develop and test ...
git add -A && git commit -m "feat: description"
git push origin feat_[feature_name]
git checkout main && git merge feat_[feature_name]
git push origin main
```

### Async Development Tips  
- Always test import errors after adding async dependencies
- Use background processes (`&`) for development server
- Monitor async function performance in browser developer tools

## Core MCP Tools

### `get_table_of_contents(path: str)`
Extracts the table of contents (bookmarks) from a PDF file.
- **Input**: Absolute path to the PDF file.
- **Output**: A list of lists, e.g., `[[1, 'Chapter 1', 10], [2, 'Section 1.1', 12]]`.
- **Errors**: Raises an exception if the file is not found, is invalid, or has no TOC.

### `get_pages_from_pdf(pdf_path: str, start_page: int, end_page: int)`
Extracts a range of pages into a new PDF.
- **Input**: Absolute path to the source PDF, 1-based start page, and 1-based end page.
- **Output**: The absolute path to the newly created PDF file (saved in the same directory as the source with 'mcp_' prefix).
- **Errors**: Raises an exception for invalid paths or page ranges.

### `get_pages_as_images(pdf_path: str, start_page: int, end_page: int, dpi: int = 150, image_format: str = "png")`
Converts a range of pages from a PDF to image files.
- **Input**: 
  - Absolute path to the source PDF
  - 1-based start page and end page
  - DPI resolution (default: 150)
  - Image format: "png" or "jpg" (default: "png")
- **Output**: A list of absolute paths to the created image files (saved in the same directory as the source with 'mcp_' prefix).
- **Errors**: Raises an exception for invalid paths, page ranges, or unsupported image formats.

### `extract_text_from_pages(pdf_path: str, start_page: int, end_page: int, markdown: bool = True)`
Extracts text from a range of pages in a PDF.
- **Input**: 
  - Absolute path to the PDF file
  - 1-based start page and end page
  - Whether to return text in Markdown format (default: True)
- **Output**: Extracted text as a string, optionally formatted as Markdown using pymupdf4llm.
- **Errors**: Raises an exception for invalid paths or page ranges.

## File & Image Handling

### Image Extraction Best Practices:
- Filter small images (< 25x25 pixels) - configured via `MIN_IMAGE_SIZE`
- Limit images per page (max 12, largest by area) - configured via `MAX_IMAGES_PER_PAGE`
- Use base64 encoding for in-memory display
- Compress to JPEG for downloads (quality: 85%) - configured via `IMAGE_COMPRESSION_QUALITY`

### Download Implementation:
- **INCORRECT**: Using HTMX for file downloads
  ```python
  hx_get="/download"  # Won't trigger browser download
  ```
- **CORRECT**: Using JavaScript
  ```python
  onclick="window.location.href='/download'"
  ```

### Configuration (`config.py`):
All tunable parameters should be in `config.py`:
- File size limits: `MAX_FILE_SIZE_MB`
- Image settings: `IMAGE_COMPRESSION_QUALITY`, `MIN_IMAGE_SIZE`, `MAX_IMAGES_PER_PAGE`
- DPI settings: `DEFAULT_DPI`, `MIN_DPI`, `MAX_DPI`
- Directories: `UPLOAD_DIR`, `DB_PATH`

## OCR Caching System

### Cache Configuration
Located in `config.py`:
- `OCR_CACHE_RETENTION_DAYS = 14` - Auto cleanup period
- `OCR_CACHE_DB_PATH` - SQLite database location
- Cache uses deterministic SHA256 hashing of base64 images

### Cache Management
```bash
# View cache statistics
# Access via web interface or direct SQLite queries
sqlite3 data/ocr_cache.db "SELECT COUNT(*) as total_entries FROM ocr_cache;"
sqlite3 data/ocr_cache.db "SELECT SUM(input_tokens + output_tokens) as tokens_saved FROM ocr_cache;"
```

### Cache Troubleshooting
- **High miss rate**: Check image consistency (DPI, compression)
- **Database locks**: Ensure proper async connection handling
- **Size growth**: Monitor auto-cleanup functionality

## Common Development Tasks

### Adding New Tools
1. Add a new method to the `PdfTools` class in `src/pdf_mcp_server/tools.py`. Implement the core pymupdf logic there.
2. Register the new method as a tool using the `@mcp.tool` decorator in `src/pdf_mcp_server/server.py`. Add a docstring and type hints.
3. Update this CLAUDE.md and README.md to document the new tool.

### Adding New Web Operations:
1. Add button in `components.py` → `operation_buttons()`
2. Create form route in `pdf.py` → `/[operation]-form/{file_hash}`
3. Create process route → `/process/[operation]/{file_hash}`
4. Add display component in `components.py`
5. Update styles in `styles.py` if needed

### FastHTML Components:
- Use `Div()`, `Button()`, `Form()` from `fasthtml.common`
- Error messages: `error_message()`, `success_message()`
- Loading indicators: Add spinner with `hx_indicator`

### Debugging
- Check the server logs for detailed error messages from PyMuPDF.
- Ensure that file paths provided to the tools are absolute and accessible by the server process.
- Page numbers are 1-based for the tool interface but must be converted to 0-based for PyMuPDF functions.

### Common Pitfalls:
- HTMX vs JavaScript for downloads (use JavaScript for file downloads)
- Page numbers are 1-based in UI but 0-based in PyMuPDF
- Always validate page ranges before processing

### Performance Considerations:
- In-memory processing with base64 is preferred for low latency
- Trade-off between image quality and file size
- Large PDFs (100+ pages) good for stress testing

## Machine Learning Experiments

### Directory Structure:
```
experiments/
├── prompts/                 # Prompt versions
├── experiment_configs/      # YAML configurations
├── results/                 # Experiment outputs
├── config.py               # ExperimentConfig class
├── utils.py                # Async/sync utilities
└── math_classification_experiment.py  # Main runner
```

### Running Experiments:
```bash
# From project root (not experiments folder):
uv run experiments/math_classification_experiment.py --config test_v3.yaml

# Quick test with subset:
uv run experiments/math_classification_experiment.py  # Uses defaults
```

### Key Configuration Parameters:
- `images_per_category: -1` for full dataset, or specific number for subset
- `concurrent_requests: 5-10` for optimal async performance
- `temperature: 0.1` for consistent classification

### Prompt Engineering Best Practices:
1. Start with baseline, iterate based on error analysis
2. Explicit negative examples more effective than positive
3. Distinguish "complete expressions" from "isolated symbols"
4. Test on subset first (10 images), then full dataset

### Math Classification Dataset:
- Location: `test_files/math_formula_dataset/`
- Structure:
  - `math_positive/`: Pages with formal mathematical equations
  - `math_negative/`: Pages without significant math (may have code, charts, specs)
- Total: ~79 images
- Manually curated to reflect user preferences

## Error Scenarios

- **FileNotFoundError**: The path provided to a tool does not exist.
- **ValueError**: 
  - A PDF does not contain a table of contents.
  - The page range provided to `get_pages_from_pdf` is invalid (e.g., start > end, or pages are out of bounds).
- **Exception: Failed to ...**: A generic wrapper for errors raised by PyMuPDF, indicating a problem with the PDF file itself (e.g., corrupted, password-protected).

### Async/Import Issues
- **"no running event loop"**: Move async calls from module import to function calls
- **aiosqlite missing**: Run `uv add aiosqlite` 
- **Background process stuck**: Use `ps aux | grep uv` and `kill [PID]`

### Performance Issues  
- **Slow OCR processing**: Check `OCR_CONCURRENT_REQUESTS` setting
- **High API costs**: Verify caching is working (check cache hit rates)
- **Memory growth**: Monitor SQLite database size and cleanup schedule

## Configuration Quick Reference

### OCR Performance Tuning
```python
# In config.py - adjust based on API rate limits
OCR_CONCURRENT_REQUESTS = 20      # Higher = faster, more API load
OCR_MAX_RETRIES = 3              # Retry failed requests  
OCR_RETRY_DELAY_BASE = 1.0       # Exponential backoff base
OCR_CACHE_RETENTION_DAYS = 14    # Balance storage vs performance
```

### Environment Setup
Required environment variables:
- LLM API keys for Gemini Flash 2.5 Lite
- Model configuration: `gemini/gemini-2.5-flash-lite`