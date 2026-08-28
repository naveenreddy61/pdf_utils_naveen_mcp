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
  - `url.py`: URL-to-Markdown and URL-to-PDF-OCR routes
  - `capture.py`: Camera capture handwriting OCR (`/capture`)
  - `api.py`: API endpoints
- **UI Components**: `src/web_app/ui/components.py` - Reusable UI elements
- **Services**: `src/web_app/services/` - Core service layer
  - `pdf_service.py`: PDF operations (extract, convert, etc.)
  - `ocr_service.py`: GenAI OCR with caching, retries, and fallback
  - `url_service.py`: URL-to-Markdown via trafilatura
  - `url_pdf_service.py`: URL-to-PDF-OCR via headless Chromium + OCR
- **Background tasks**: `src/web_app/core/tasks.py` - in-process store for jobs
  that outlive one HTTP request (see below)
- **Styles**: `src/web_app/ui/styles.py` - CSS styles

### Long-running operations (`core/tasks.py`)

Whole-document OCR and chapter OCR run for minutes — too long for a single POST
(dead spinner, proxy read timeout). Both follow the same shape:

1. The POST validates, calls `tasks.start_task(work)` and returns
   `task_progress_poll(task_id, status_url, label, pct)` immediately.
2. `work(task_id)` runs in the background and calls `tasks.set_progress(...)`;
   its return value is stored as the task result.
3. A status route (`/ocr-status/...`, `/chapters-status/...`) is polled every
   750 ms and returns either a fresh progress bar or the final result fragment.
   The final swap carries no polling attributes, so the loop ends itself.

Page-level granularity comes from `process_document_async(..., page_progress=cb)`,
where `cb(done, total)` fires as each page completes. Pages are dispatched
concurrently, so this is a completion count, not a page walk-through.

The store is per-process and in-memory — a restart loses in-flight jobs, which
is fine because the work is re-runnable and the OCR cache makes a rerun cheap.

### Upload transports (`routes/main.py`)

There are two ways bytes reach the server, chosen in the browser by file size:

| | ≤ `GCS_DIRECT_THRESHOLD_MB` (5) | above it |
|---|---|---|
| route | `POST /upload` multipart | `/api/request-upload` → PUT to GCS → `/api/confirm-upload` |
| why | one transfer, no cloud account | Cloudflare and nginx both cap a body at 100 MB |

The threshold sits far below the 100 MB it guards, on purpose: the cloud route
is the half that fails silently (stale key, dropped CORS rule), and a path only
taken by rare huge files is one you find broken at the worst moment.

Both then call the **same** `_run_upload_task`, which is the point: PPTX/Markdown
conversion, page counting and the polling progress UI must not depend on
how the file arrived. `_run_gcs_upload_task` only fetches the object and
delegates. Markdown is the exception on **dedup**: it is hashed before
conversion, so a renderer change would otherwise keep serving the old PDF.
`.md` always reconverts and overwrites the stored file.

Things that will bite you here:

- **`fetch()` does not send `HX-Request`**, so FastHTML wraps a returned
  component in a full HTML page. Anything the direct-upload JS calls must return
  `_fragment(...)` (an explicit `HTMLResponse(to_xml(...))`). This bug shipped
  once already (`f5cc2a7`).
- **`htmx.process()` is mandatory** after assigning `innerHTML` from JS — htmx
  never scans nodes it didn't insert, so the polling fragment would sit there
  inert.
- **Routing lives in one `htmx:beforeRequest` handler** on the file input, not in
  the drop/paste handlers. The native file picker fires `change` → htmx posts
  immediately, so a size check anywhere else is bypassed by simply clicking
  "Choose File".
- **`/api/request-upload` must check `MAX_FILE_SIZE_GCS_BYTES`**, not
  `MAX_FILE_SIZE_BYTES`. Checking the multipart cap there is what made the
  original bypass unable to accept anything the multipart path couldn't — the
  feature was live for 19 hours in Feb 2026 and could never have worked.
- **The whole file is held in memory** while hashing, on both paths. That, not
  bandwidth, is what bounds `MAX_FILE_SIZE_GCS_MB`.

### Local mode (`--local`)

`pdf-web-app --local` sets `PDF_LOCAL_MODE=1` **before** the first
`pdf_utils.config` import — config reads env at import time and every module does
`from pdf_utils.config import ...`, so setting it later would not propagate.
Local mode binds `127.0.0.1` (auth is off whenever `LOGIN_PASSWORD` is unset,
so `0.0.0.0` would expose an open app to the LAN), forces `GCS_BUCKET_NAME` empty
regardless of `.env`, and raises the upload cap to 500 MB since no proxy is in
the way.

### Operation form / result split

`operation_buttons()` renders two slots: ops-grid buttons load forms into
`#operation-form`, and those forms submit into `#operation-result` below. This
keeps a form on screen after it runs, so a page range can be tweaked and
resubmitted without re-opening it. A bubbling `hx-on::before-request` handler on
the grid clears `#operation-result` when a different operation is selected.

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
- htmx **cancels the native submit** for a `<button>` inside a `<form>`, which
  also suppresses the browser's validation bubble. A button carrying its own
  `hx-post` must call `this.form.reportValidity()` in `onclick` and
  `event.stopImmediatePropagation()` on failure (see `url_input_form()`), or
  `required` / `type="url"` silently do nothing.
- For server-saved files: `window.location.href='/download/route/filename'`
- For clipboard copy of large content: `fetch('/download/route/filename').then(r=>r.text()).then(t=>navigator.clipboard.writeText(t))`
  (do NOT read from DOM `.textContent` — browser clipboard API has size limits)
- Images are served from `uploads/` directory
- In-memory processing preferred for performance

## URL Processing Architecture

The app exposes three URL-based modes from the main page. Two extract *text from
a web page*; the third produces an *uploaded file*, which is why it gets its own
box rather than a third button on the URL card.

### PDF-from-URL (`pdf_url_service.py`)
For links that point straight at a PDF (`…/w35559.pdf`). The server downloads
the bytes, then hands them to the same `_run_upload_task` the file picker uses,
so the result is an ordinary uploaded PDF with the full toolset available.
- Route: `POST /process/pdf-from-url` → returns `upload_progress_poll(...)`,
  polled at `/upload-status/{task_id}` like any other upload
- **Validation is on the bytes, not the suffix** (`%PDF-` magic). A `.pdf` URL
  behind a paywall or login wall returns HTML with a 200, and registering that
  as a PDF fails later and less legibly.
- **SSRF guard**: the server dereferences a user-supplied URL, so every hop's
  host is resolved and rejected if it maps to a private/loopback/link-local
  address. Redirects are therefore followed **manually** (`follow_redirects=False`
  plus a loop) — letting httpx follow them would skip the check on hops 2..n.
- The body is streamed with a running byte count so an oversized response is cut
  off mid-transfer, not after it is already in memory. Cap is
  `EFFECTIVE_MAX_UPLOAD_MB` (no proxy sits in this path — the bytes arrive
  server-side).
- A browser `User-Agent` is sent (`PDF_URL_USER_AGENT`); several publishers 403 a
  bare client.

The two extraction modes:

### URL-to-Markdown (`url_service.py`)
Uses **trafilatura** to fetch and extract article text from any URL.
- Runs sync trafilatura in a thread pool via `asyncio.to_thread()`
- Returns `UrlExtractionResult` with title, clean markdown, word/char counts
- Route: `POST /process/url-to-markdown` → download at `GET /download/url-md/{filename}`

### URL-to-PDF-OCR (`url_pdf_service.py`)
Full pipeline: headless browser → PDF → LLM OCR. Handles JS-heavy pages, cookie banners, and pop-ups.

**Pipeline steps:**
1. **Browser capture** (`_capture_pdf_async`): Launch headless Chromium via Playwright, dismiss consent banners (CSS injection + JS button clicking), print page to PDF bytes
2. **Quality check** (`check_pdf_quality`): Extract first 2 pages with PyMuPDF, ask Gemini to classify as GOOD / POOR / BLOCKED
3. **Retry capture** (if POOR/BLOCKED): Re-run with aggressive CSS that hides all fixed/sticky overlays
4. **OCR** (`process_document_async` from `ocr_service.py`): Full GenAI OCR with caching and retries
5. **Result**: `UrlPdfOcrResult` with quality badge, page/token metrics, and full extracted text
- Route: `POST /process/url-to-pdf-ocr` → download at `GET /download/url-pdf-text/{filename}`

### Playwright / Headless Chromium Setup

**Install (one-time):**
```bash
# Install Playwright Python package
uv add playwright

# Download the headless Chromium browser binary (~200 MB)
uv run playwright install chromium

# Install required OS-level system dependencies
uv run playwright install-deps chromium
```

**Or use the Makefile target:**
```bash
make install-playwright
```

**Verify Chromium is available:**
```bash
make chrome-path
# Expected: /root/.cache/ms-playwright/chromium-XXXX/chrome-linux/chrome

make test-env
# Checks API key + GenAI import + Playwright binary
```

**On Debian/Ubuntu VPS without GUI (headless is fine):**
```bash
# Install OS deps that Chromium needs to run headlessly
uv run playwright install-deps chromium
# This installs packages like: libnss3, libatk1.0-0, libgbm1, etc.
```

**Configuration (`config.py`):**
```python
URL_PDF_BROWSER_TIMEOUT = 30000      # ms: page load timeout
URL_PDF_PRINT_WAIT_MS   = 1500       # ms: delay after scroll (lets pop-ups appear)
URL_PDF_QUALITY_CHECK_ENABLED = True # LLM quality assessment before full OCR
URL_PDF_CHROMIUM_EXECUTABLE = ""     # leave empty to use playwright's own binary
```

## Camera Capture Handwriting OCR (`routes/capture.py`)

Transcribes a handwritten paper notebook held up to a webcam or tablet camera. Solves the
"photo on phone → cloud sync → download → attach to a chat" round trip: open `/capture`,
hold each page up, Capture then Next page, Done, text on the clipboard.

**Routes:**
- `GET /capture` → the capture page (live preview, Capture / Retake / Next page / Done)
- `POST /process/notebook-page` → one frame in, JSON `{ok, task_id}` out; OCR starts in
  the background so the user can line up the next page
- `GET /notebook-page-status/{task_id}` → JSON chip status (`pending` / `done` / `error`)
- `GET /notebook-session-status?ids=` → JSON summary of every accepted page
- `GET /notebook-session-result?ids=` → HTML result panel once every page is terminal

**Pipeline:** `getUserMedia` preview → `<canvas>` frame grab at native resolution →
`toBlob` JPEG (`CAPTURE_JPEG_QUALITY`) → **Next page** or **Done** POSTs the blob and
starts `ocr_image_bytes()` as a `tasks.start_task` job. Done polls until every task is
terminal, then renders per-page textareas + Copy all (joined with `--- page break ---`).

**Design decisions worth preserving:**
- **Nothing touches disk.** Unlike the upload flow, the frame and the transcription are
  never persisted. `fast_app(static_path='uploads')` serves that directory statically, so
  writing notebook photos there would expose them needlessly.
- **Cache is bypassed** (`use_cache=False`). Camera frames are never byte-identical, so
  lookups always miss while still writing personal notes into the 60-day cache.
- **Camera lives on its own page, not the index.** An embedded preview on `/` would trigger
  a camera permission prompt on every visit for every unrelated PDF task.
- **Copy reads from the textarea**, deliberately deviating from the "fetch text from a
  download route" convention below. That rule exists for large PDF transcriptions; a
  notebook session is a few KB, and reading the textareas preserves the user's manual
  edits. Copy all joins captures with `--- page break ---`.
- **OCR starts on Next page / Done, not on Capture.** Capture only freezes the frame so
  Retake is free. The accepted blob is posted and `tasks.start_task` runs while the
  camera goes live again. Tasks are not popped after the first read, so adding another
  page and pressing Done again still sees pages 1–N.
- **Prompt is tuned against two specific failure modes** — the model double-spacing output
  because it reads the notebook's printed ruled lines as blank lines, and dropping the
  indentation of nested lines. Both regressed visibly when the prompt was looser; keep the
  explicit instructions in `prompts/ocr_prompt_handwriting.txt`.
- **One page or a two-page spread** is auto-detected by looking for the binding gutter. Two
  pages are separated by a line containing only `--- page break ---`.
- Uncertain words are marked `[?]`, unreadable ones `[illegible]`, cut-off ones `[cut off]`,
  so the author knows exactly where to check rather than trusting a confident guess.

**Browser requirements:** `getUserMedia` and `navigator.clipboard` both require a secure
context — HTTPS or localhost. The page checks `window.isSecureContext` up front and shows an
explanatory message rather than failing silently. Camera tracks are stopped on `pagehide` so
the hardware indicator light goes out.

## Markdown-to-PDF Conversion (`md_service.py`)

The home page has a dedicated **Markdown to PDF** card below Notebook OCR. `.md` is **not** accepted on the top drop zone (`POST /upload` tells the user to use the card). The card uses the same click/drop/paste-file + GCS split as other uploads (`POST /process/md-to-pdf` under 5 MB; signed URL above). Conversion is `md-render-pipeline/render.sh` (perl cleanup, optional KaTeX empty-`\sqrt{}`, `bar-to-overline.lua`, pandoc GFM + Typst). Result is stored as `file_type="pdf"` on disk, then uploaded to `temp-downloads/` and auto-downloaded via a signed GCS GET (local `/{filename}` if GCS is off). Same `.md` always reconverts. Cap: 8 MB (`MAX_MD_SIZE_MB`), timeout 120 s (`MD_RENDER_TIMEOUT`). Path: `MD_RENDER_SCRIPT` or sentinel-bounded repo root (`pyproject.toml` / `.git`). Subprocess: argv, `cwd` = temp dir, SIGTERM then SIGKILL.

**System dependencies (not managed by `uv`):**
- `pandoc` — `apt install pandoc`
- `typst` CLI — prebuilt binary (not in apt):
  ```bash
  curl -fsSL -o /tmp/typst.tar.xz https://github.com/typst/typst/releases/latest/download/typst-x86_64-unknown-linux-musl.tar.xz
  tar -xf /tmp/typst.tar.xz -C /tmp
  install -m 755 /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst
  ```
- Fonts — pipeline uses Typst-embedded **New Computer Modern** (body + headings) and **New Computer Modern Math**, with JetBrainsMono NF for code (DejaVu Sans Mono fallback). That is the LaTeX Computer Modern look; do not switch headings back to a sans family. `apt-get install -y fonts-dejavu` on a new host for the code fallback. Edit `typst-header.typ` / `render.sh` only to change this style or if a `typst fonts` probe fails.
- Math auto-fix: `cd md-render-pipeline && npm ci --omit=dev` (katex). Without it, `render.sh` continues and skips the empty-`\sqrt{}` fix.

**Verify:**
```bash
pandoc --version && typst --version
./md-render-pipeline/render.sh /tmp/t.md /tmp/t.pdf
python -c "p=open('/tmp/t.pdf','rb').read(); assert p.startswith(b'%PDF')"
uv run python tests/test_md_service.py
```

## Prerequisites

- **Python 3.12+**: Required for the server.
- **uv**: Recommended for environment and package management.
- **Playwright Chromium**: Required for URL-to-PDF-OCR feature (see above).
- **pandoc + typst**: Required for Markdown-to-PDF upload conversion (see above).

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

### Makefile Quick Reference

A `Makefile` at the project root wraps all common workflows:

```bash
make dev                  # Start local dev server
make install              # Install all dependencies (uv sync)
make install-playwright   # Install Playwright + headless Chromium
make chrome-path          # Print path to Playwright's Chromium binary
make test                 # Run OCR service test suite
make test-env             # Verify API key + GenAI + Playwright
make restart              # Restart VPS pdf-app service
make logs                 # Tail live VPS logs
make logs-100             # Last 100 log lines
make deploy               # git push + restart VPS service
make build                # Build distributable wheel
make db-stats             # OCR cache row count + token savings
make db-clear             # Delete OCR cache (forces full re-OCR)
make clean                # Remove build artifacts
```

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
- **Google GenAI Client**: Direct PDF processing with the `gemini-flash-lite-latest` stub
- **PDF Chunking**: Configurable page grouping (default: 2 pages per API call)
- **Stable Caching**: File-based cache keys for deterministic performance
- **Async Batch Processing**: Semaphore-controlled concurrent requests

### Key Configuration:
```python
# config.py
OCR_MODEL = "gemini-flash-lite-latest"   # Stub: tracks newest Flash-Lite release
OCR_THINKING_LEVEL = "MINIMAL"           # Measured best; see note below
# OCR processes one page at a time for simplicity and reliability
OCR_CONCURRENT_REQUESTS = 50             # Rate limiting for API calls
OCR_MAX_TOKENS = 4096                    # Per-page token limit

HANDWRITING_OCR_MODEL = "gemini-flash-latest"   # Camera capture uses the full Flash tier
HANDWRITING_THINKING_LEVEL = "LOW"             # MINIMAL is rejected by this stub, see below
```

### Gemini 3.x parameter rules (important)
- **`temperature`, `top_p`, `top_k` are deprecated.** Gemini 3.x accepts them but silently
  ignores them, and future generations will return HTTP 400. Do not reintroduce them.
  Determinism comes from the **system instruction** instead.
- **Prompts go in `system_instruction`**, not `contents[0]`. Build every OCR call's config
  with `ocr_service.build_ocr_config(system_instruction, thinking_level=..., max_output_tokens=...)`
  so all call sites stay consistent.
- **Set `thinking_level` explicitly** (`MINIMAL` / `LOW` / `MEDIUM` / `HIGH`). Defaults vary
  by tier — Flash-Lite defaults to minimal, Flash to medium — so relying on the default
  makes cost and latency change silently when a stub moves.
- **Use the lowest level the model accepts, and do not raise it without measuring.** Across
  5 handwritten pages x 2 models x 3 levels x 2 runs, more thinking made transcription
  *worse*: flash MINIMAL 96.5% / LOW 92.2% / MEDIUM 80.5%; flash-lite MINIMAL 92.6% /
  LOW 88.7% / MEDIUM 89.0%. MEDIUM also costs ~8x and ~8x the latency, and has a failure
  mode where the model emits its own letter-by-letter deliberation as the transcription.
  Transcription is perception, not reasoning — extra budget gets spent second-guessing
  correct readings.
- **Not every tier accepts every level, and this changes under you.** On 2026-08-14
  `gemini-flash-latest` began returning `400 INVALID_ARGUMENT: Thinking level MINIMAL is
  not supported for this model`, breaking every `/capture` transcription; handwriting is
  now on `LOW`. Flash-Lite still accepts MINIMAL, so print OCR was untouched — the split
  knobs did their job. When a stub moves, probe the levels before assuming a config value
  still applies.
- **Count thinking tokens.** They are billed as output but arrive in a separate
  `thoughts_token_count` field. Use `extract_token_usage(response)`; reading
  `candidates_token_count` alone understated cost by ~3x at MEDIUM.
- **Model stubs auto-upgrade.** `-latest` stubs follow Google's newest release in that tier.
  Print and handwriting are on separate knobs so a regression in one cannot degrade the other.

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