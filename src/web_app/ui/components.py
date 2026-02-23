"""UI components for the web application."""

from fasthtml.common import *
from pdf_utils.config import MAX_FILE_SIZE_MB


# ── Upload ──────────────────────────────────────────────────────────────────

def upload_form():
    """HTMX-native upload – uses a <label for=...> to open the file picker.

    Clicking the visible "Choose File" button triggers the native OS file
    dialog via the browser's built-in label→input association (no JS needed).
    When a file is chosen, `hx-trigger="change from:#file-input"` on the
    Form auto-submits as multipart/form-data to /upload.
    """
    return Div(
        Form(
            # ── Upload card ───────────────────────────────────────────────
            Div(
                P("📁", cls="upload-icon"),
                # The Label opens the file picker when clicked – 100% reliable
                Label(
                    "Choose File",
                    for_="file-input",
                    cls="upload-browse-btn",
                ),
                P(f"PDF · JPG · PNG · WEBP  ·  max {MAX_FILE_SIZE_MB} MB",
                  cls="upload-hint"),
                cls="upload-zone",
            ),
            # Hidden input – opened by the Label above, never clicked directly
            Input(
                type="file",
                name="file",
                id="file-input",
                accept=".pdf,.jpg,.jpeg,.png,.webp",
                style="display:none;",
            ),
            # ── In-flight indicator (shown by HTMX during HTTP POST) ──────
            Div(
                Span(cls="spinner"),
                Span("Uploading…"),
                id="upload-indicator",
            ),
            # HTMX submits the form whenever the hidden input fires `change`
            hx_post="/upload",
            hx_encoding="multipart/form-data",
            hx_trigger="change from:#file-input",
            hx_target="#upload-result",
            hx_swap="innerHTML",
            hx_indicator="#upload-indicator",
        ),
        Div(id="upload-result"),
        cls="upload-section",
    )


def upload_progress_poll(task_id: str):
    """Polling container returned immediately after POST /upload.

    Self-replaces every 250 ms via hx-trigger until the server
    signals completion (at which point the final content has no
    polling attributes and the loop stops automatically).
    """
    return Div(
        _progress_bar("Saving file…", 10),
        id="upload-poll",
        hx_get=f"/upload-status/{task_id}",
        hx_trigger="every 250ms",
        hx_target="this",
        hx_swap="outerHTML",
    )


def upload_progress_status(phase: str, pct: int):
    """Progress bar used inside the polling container."""
    return _progress_bar(phase, pct)


def _progress_bar(label: str, pct: int):
    return Div(
        Div(
            Span(cls="spinner"),
            Span(label),
            cls="progress-phase",
        ),
        Div(
            Div(style=f"width:{pct}%", cls="progress-fill"),
            cls="progress-track",
        ),
        cls="upload-progress",
    )


# ── Page wrapper ────────────────────────────────────────────────────────────

def page_with_result(result_content):
    """Full page - kept for backward compatibility in error paths."""
    return Titled("PDF & Image Utilities",
        Div(
            Div(
                H1("PDF & Image Utilities", cls="page-title"),
                P("Upload a PDF or image to use processing tools.",
                  cls="page-subtitle"),
                cls="page-header",
            ),
            upload_form(),
            result_content,
            cls="app-wrap",
        )
    )


# ── File info ────────────────────────────────────────────────────────────────

def file_info_display(file_info, is_existing=False):
    """Compact pill-based file info card."""
    is_pdf = file_info.file_type == "pdf"
    icon   = "📄" if is_pdf else "🖼"
    label  = "PDF" if is_pdf else "Image"
    size   = f"{file_info.file_size / 1024 / 1024:.1f} MB"

    pills = [
        Span(f"{icon} {label}", cls="pill"),
        Span(size, cls="pill"),
    ]
    if is_pdf:
        pills.append(Span(f"{file_info.page_count} pages", cls="pill"))

    status_msg = "Uploaded" if not is_existing else "Already cached – instant load"
    status_cls = "alert-success" if not is_existing else "alert-warning"

    return Div(
        P(file_info.original_filename, cls="file-name"),
        Div(*pills, cls="file-meta"),
        P(status_msg, cls=status_cls),
        cls="card",
        style="margin-bottom:0.75rem;",
    )


# ── Operation buttons ────────────────────────────────────────────────────────

def operation_buttons(file_hash, file_type="pdf"):
    """Responsive CSS-grid of operation buttons with icon + label."""
    if file_type == "image":
        return Div(
            H3("Operations"),
            Div(
                _op_btn("🤖", "OCR",
                        hx_get=f"/extract-text-llm-image/{file_hash}",
                        hx_target="#operation-result",
                        extra_cls="purple"),
                cls="ops-grid",
            ),
            Div(id="operation-result"),
        )

    return Div(
        H3("Operations"),
        Div(
            _op_btn("📑", "TOC",
                    hx_post=f"/process/toc/{file_hash}",
                    hx_target="#operation-result"),
            _op_btn("✂️", "Extract Pages",
                    hx_get=f"/extract-pages-form/{file_hash}",
                    hx_target="#operation-result"),
            _op_btn("🖼", "To Images",
                    hx_get=f"/convert-images-form/{file_hash}",
                    hx_target="#operation-result"),
            _op_btn("📝", "Text",
                    hx_get=f"/extract-text-form/{file_hash}",
                    hx_target="#operation-result"),
            _op_btn("🎨", "Images",
                    hx_get=f"/extract-images-form/{file_hash}",
                    hx_target="#operation-result",
                    extra_cls="green"),
            _op_btn("🤖", "OCR",
                    hx_get=f"/extract-text-llm-form/{file_hash}",
                    hx_target="#operation-result",
                    extra_cls="purple"),
            cls="ops-grid",
        ),
        Div(id="operation-result"),
    )


def _op_btn(icon: str, label: str, extra_cls: str = "", **htmx_attrs):
    """Single operation button: icon on top, short label below."""
    cls = f"op-btn {extra_cls}".strip()
    return Button(
        Span(icon, cls="op-icon"),
        Span(label),
        cls=cls,
        **htmx_attrs,
    )


# ── TOC ──────────────────────────────────────────────────────────────────────

def toc_display(toc):
    if not toc:
        return Div(
            H3("Table of Contents"),
            P("This PDF has no table of contents.", cls="warning"),
            cls="result-area",
        )

    items = []
    for level, title, page in toc:
        level_cls = f"toc-l{min(level, 3)}"
        bold = "font-weight:700;" if level == 0 else ""
        items.append(
            Li(
                Span(title, cls="toc-title"),
                Span(f"p. {page}", cls="toc-page"),
                cls=f"toc-item {level_cls}",
                style=bold,
            )
        )

    return Div(
        H3("Table of Contents"),
        Ul(*items, cls="toc-list"),
        cls="result-area",
    )


# ── Alerts ───────────────────────────────────────────────────────────────────

def error_message(message):
    return P(message, cls="error")


def success_message(message):
    return P(message, cls="success")


def warning_message(message):
    return P(message, cls="warning")


# ── Image gallery ─────────────────────────────────────────────────────────────

def image_extraction_gallery(images_data, file_hash, start_page, end_page):
    if not images_data:
        return Div(
            H3("No Images Found"),
            P("No images found in the specified page range.", cls="warning"),
            cls="result-area",
        )

    gallery_elements = []
    total_images = 0

    for page_num in sorted(images_data.keys()):
        page_images = images_data[page_num]
        if not page_images:
            continue

        gallery_elements.append(
            Div(f"Page {page_num}", cls="page-separator")
        )

        image_items = []
        for img_data in page_images:
            total_images += 1
            image_items.append(
                Div(
                    A(
                        Img(
                            src=img_data["data"],
                            alt=img_data["filename"],
                            cls="image-thumbnail",
                        ),
                        href=img_data["data"],
                        download=img_data["filename"],
                        title=f"Download {img_data['filename']}",
                    ),
                    cls="image-item",
                )
            )

        gallery_elements.append(
            Div(*image_items, cls="image-extraction-grid")
        )

    return Div(
        H3("Extracted Images"),
        Div(
            Span(f"{total_images} images from pages {start_page}–{end_page}",
                 cls="pill"),
            cls="file-meta",
            style="margin-bottom:0.75rem;",
        ),
        P("Click any image to download it",
          style="font-size:0.8rem; color:var(--text-muted); margin-bottom:0.5rem;"),
        Div(
            Button(
                "⬇ Download All as ZIP",
                onclick=(
                    f"this.textContent='Preparing…'; this.disabled=true;"
                    f"window.location.href='/download-image-zip/{file_hash}/{start_page}/{end_page}';"
                    f"setTimeout(()=>{{this.textContent='⬇ Download All as ZIP';this.disabled=false;}},2000);"
                ),
                cls="button",
            ),
            cls="action-row",
        ),
        Div(*gallery_elements, cls="image-gallery-container"),
        cls="result-area",
    )


# ── OCR result ───────────────────────────────────────────────────────────────

def ocr_result_display(results, file_hash, start_page, end_page, text_filename):
    preview_id = f"ocr-preview-{file_hash}-{start_page}-{end_page}"

    cached_pages  = results.get("cached_pages", [])
    llm_pages     = results.get("llm_pages", [])
    fallback_pages = results.get("fallback_pages", [])
    pages_done    = results.get("pages_processed", 0)
    cache_rate    = (len(cached_pages) / pages_done * 100) if pages_done else 0
    proc_time     = results.get("processing_time", 0)
    in_tok        = results.get("total_input_tokens", 0)
    out_tok       = results.get("total_output_tokens", 0)

    # ── metrics boxes ──────────────────────────────────────────────────────
    metrics = Div(
        Div(
            P("⏱ Time", cls="metric-label"),
            P(f"{proc_time:.1f}s", cls="metric-value"),
            cls="metric-box",
        ),
        Div(
            P("💾 Cache", cls="metric-label"),
            P(f"{cache_rate:.0f}%", cls="metric-value"),
            cls="metric-box",
        ),
        Div(
            P("🔤 Input tok", cls="metric-label"),
            P(f"{in_tok:,}", cls="metric-value"),
            cls="metric-box",
        ),
        Div(
            P("🔤 Output tok", cls="metric-label"),
            P(f"{out_tok:,}", cls="metric-value"),
            cls="metric-box",
        ),
        cls="metrics-row",
    )

    # ── per-page detail list ───────────────────────────────────────────────
    page_items = []
    if "processing_details" in results:
        for d in results["processing_details"]:
            m = d["method"]
            icon  = {"Cached": "💾", "LLM OCR": "🤖", "PyMuPDF Fallback": "📄"}.get(m, "❌")
            color = {"Cached": "#17a2b8", "LLM OCR": "#16a34a",
                     "PyMuPDF Fallback": "#ea580c"}.get(m, "#dc2626")
            tok = d["tokens"]["input"] + d["tokens"]["output"]
            tok_txt = f" · {tok:,} tok" if tok else ""
            retry_txt = f" (retry {d['retry_count']})" if d.get("retry_count") else ""
            page_items.append(Li(
                f"{icon} Page {d['page']}: {m}{retry_txt}{tok_txt}",
                style=f"color:{color}",
            ))
    else:
        for p in cached_pages:
            page_items.append(Li(f"💾 Page {p}: Cached",        style="color:#17a2b8"))
        for p in llm_pages:
            page_items.append(Li(f"🤖 Page {p}: LLM OCR",       style="color:#16a34a"))
        for p in fallback_pages:
            page_items.append(Li(f"📄 Page {p}: PyMuPDF",       style="color:#ea580c"))

    # ── progress messages ──────────────────────────────────────────────────
    prog_section = []
    if results.get("progress_messages"):
        prog_section = [Div(
            H4("Processing log"),
            Ul(*[Li(m, style="font-size:0.85rem;color:var(--text-muted);padding:0.15rem 0;")
                 for m in results["progress_messages"]],
               style="list-style:none;padding:0;"),
            style="background:var(--surface-alt);border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem;margin-bottom:0.75rem;",
        )]

    return Div(
        P(results.get("summary", "OCR complete"),
          cls="alert-success"),

        metrics,

        *prog_section,

        # page-by-page
        Div(
            H4("Per-page detail"),
            Ul(*page_items, cls="page-detail-list"),
            style="background:var(--surface-alt);border:1px solid var(--border);border-radius:var(--radius);padding:0.75rem;margin-bottom:0.75rem;",
        ),

        # char count / failures
        Div(
            Span(f"{len(results['full_text']):,} characters",
                 cls="pill"),
            *([Span(f"⚠ {len(results.get('failed_pages',[]))} page(s) failed",
                    cls="pill",
                    style="border-color:var(--red);color:var(--red);")]
              if results.get("failed_pages") else []),
            cls="file-meta",
            style="margin-bottom:0.75rem;",
        ),

        # action buttons
        Div(
            A("⬇ Download Text",
              href=f"/{text_filename}",
              download=text_filename,
              cls="button",
              style="background:var(--green);"),
            Button(
                "📋 Copy",
                onclick=(
                    f"const t=document.getElementById('{preview_id}').textContent;"
                    f"navigator.clipboard.writeText(t).then(()=>{{"
                    f"this.textContent='✅ Copied!';this.style.background='var(--green)';"
                    f"setTimeout(()=>{{this.textContent='📋 Copy';this.style.background='';}},2000);}});"
                ),
                cls="button",
            ),
            cls="action-row",
        ),

        H4("Preview"),
        Pre(results["full_text"],
            id=preview_id,
            cls="text-preview"),

        cls="result-area",
    )
