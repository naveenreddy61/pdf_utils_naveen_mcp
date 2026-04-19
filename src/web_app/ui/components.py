"""UI components for the web application."""

from fasthtml.common import *
from pdf_utils.config import MAX_FILE_SIZE_MB


# ── Upload ──────────────────────────────────────────────────────────────────

def upload_form():
    """Upload zone with a styled label button over a hidden file input.

    Clicking the label opens the OS file dialog (standard label behaviour).
    HTMX listens for `change` on the hidden input and posts as multipart/form-data.
    The label is a plain inline-block so flexbox centers it perfectly under the icon.
    """
    return Div(
        Form(
            # ── Upload card ───────────────────────────────────────────────
            Div(
                P("📁", cls="upload-icon"),
                # Styled label acts as the visible "Choose File" button
                Label(
                    "Choose File",
                    Input(
                        type="file",
                        name="file",
                        accept=".pdf,.jpg,.jpeg,.png,.webp,.ppt,.pptx",
                        style="display:none",
                        hx_post="/upload",
                        hx_encoding="multipart/form-data",
                        hx_trigger="change",
                        hx_target="#upload-result",
                        hx_swap="innerHTML",
                        hx_indicator="#upload-indicator",
                    ),
                    cls="file-label-btn",
                ),
                P(f"PDF · PPT · JPG · PNG · WEBP  ·  max {MAX_FILE_SIZE_MB} MB",
                  cls="upload-hint"),
                cls="upload-zone",
            ),
            # ── In-flight indicator (shown by HTMX during HTTP POST) ──────
            Div(
                Span(cls="spinner"),
                Span("Uploading…"),
                id="upload-indicator",
            ),
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
            _op_btn("🤖", "OCR",
                    hx_get=f"/extract-text-llm-form/{file_hash}",
                    hx_target="#operation-result",
                    extra_cls="purple"),
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
            _op_btn("📚", "Chapters",
                    hx_get=f"/download-chapters-form/{file_hash}",
                    hx_target="#operation-result",
                    extra_cls="orange"),
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


# ── URL to Markdown ──────────────────────────────────────────────────────────

def url_input_form():
    """URL input section — card below the file upload."""
    return Div(
        # ── divider ──────────────────────────────────────────────────────
        Div(
            Div(cls="or-line"),
            Span("or extract from a URL", cls="or-label"),
            Div(cls="or-line"),
            cls="or-divider",
        ),
        # ── URL to Markdown card ──────────────────────────────────────────
        Div(
            Div(
                Span("🔗", cls="url-section-icon"),
                Div(
                    P("URL to Markdown", cls="url-section-title"),
                    P("Paste any article, blog post, or docs page",
                      cls="url-section-sub"),
                    cls="url-section-text",
                ),
                cls="url-section-header",
            ),
            Form(
                Input(
                    type="text",
                    name="url",
                    placeholder="https://example.com/article",
                    autocomplete="off",
                    style="margin-bottom:0.5rem;",
                ),
                Button(
                    "Convert to Markdown",
                    type="submit",
                    style="width:100%;justify-content:center;margin-bottom:0.625rem;",
                ),
                Div(
                    Label(
                        Input(type="checkbox", name="include_links",  value="on", checked=True),
                        " Links",
                    ),
                    Label(
                        Input(type="checkbox", name="include_tables", value="on", checked=True),
                        " Tables",
                    ),
                    Label(
                        Input(type="checkbox", name="include_images", value="on"),
                        " Images",
                    ),
                    Div(
                        Span(cls="spinner"),
                        Span("Fetching…"),
                        id="url-indicator",
                        cls="htmx-indicator",
                        style="color:var(--primary);font-size:0.8rem;font-weight:500;gap:0.35rem;",
                    ),
                    cls="url-options",
                ),
                hx_post="/process/url-to-markdown",
                hx_target="#url-result",
                hx_swap="innerHTML",
                hx_indicator="#url-indicator",
            ),
            cls="url-card",
        ),
        Div(id="url-result"),
        # ── URL to PDF OCR card ───────────────────────────────────────────
        Div(
            Div(
                Span("🖨️", cls="url-section-icon"),
                Div(
                    P("URL via Browser + OCR", cls="url-section-title"),
                    P("Renders page in headless Chrome, prints to PDF, then runs AI OCR — handles JS, cookie banners & pop-ups",
                      cls="url-section-sub"),
                    cls="url-section-text",
                ),
                cls="url-section-header",
            ),
            Form(
                Input(
                    type="text",
                    name="url",
                    placeholder="https://example.com/article",
                    autocomplete="off",
                    style="margin-bottom:0.5rem;",
                ),
                Button(
                    "Convert via Browser (OCR)",
                    type="submit",
                    style="width:100%;justify-content:center;margin-bottom:0.625rem;background:var(--purple);",
                ),
                Div(
                    Div(
                        Span(cls="spinner"),
                        Span("Rendering page…"),
                        id="url-pdf-indicator",
                        cls="htmx-indicator",
                        style="color:var(--purple);font-size:0.8rem;font-weight:500;gap:0.35rem;",
                    ),
                    cls="url-options",
                ),
                hx_post="/process/url-to-pdf-ocr",
                hx_target="#url-pdf-result",
                hx_swap="innerHTML",
                hx_indicator="#url-pdf-indicator",
            ),
            cls="url-card",
            style="margin-top:0.75rem;",
        ),
        Div(id="url-pdf-result"),
    )


def url_result_display(result, md_filename: str, file_content: str):
    """Result panel for URL extraction."""
    preview_id = f"url-preview-{md_filename[:12]}"
    return Div(
        # ── header ───────────────────────────────────────────────────────
        Div(
            *([P(result.title, cls="url-result-title")] if result.title else []),
            P(result.url, cls="url-result-source"),
            cls="url-result-header",
        ),
        # ── metrics ──────────────────────────────────────────────────────
        Div(
            Div(
                P("Characters", cls="metric-label"),
                P(f"{result.char_count:,}", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Words", cls="metric-label"),
                P(f"{result.word_count:,}", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Time", cls="metric-label"),
                P(f"{result.processing_time:.1f}s", cls="metric-value"),
                cls="metric-box",
            ),
            cls="metrics-row",
            style="margin-bottom:0.875rem;",
        ),
        # ── actions ──────────────────────────────────────────────────────
        Div(
            A(
                "⬇ Download .md",
                href=f"/{md_filename}",
                download=md_filename,
                cls="button",
                style="background:var(--green);",
            ),
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
        # ── preview (shows the full file content with source header/footer) ──
        H4("Preview"),
        Pre(file_content, id=preview_id, cls="text-preview"),
        cls="result-area",
    )


def url_pdf_ocr_result_display(result, txt_filename: str, file_content: str):
    """Result panel for URL-to-PDF-OCR extraction."""
    preview_id = f"url-pdf-preview-{txt_filename[:16]}"

    # Quality badge styling
    quality_colors = {
        "GOOD":    ("var(--green)",   "var(--green-light)"),
        "POOR":    ("var(--orange)",  "var(--orange-light)"),
        "BLOCKED": ("var(--red)",     "var(--red-light)"),
        "UNKNOWN": ("var(--text-muted)", "var(--surface-alt)"),
    }
    q = result.quality or "UNKNOWN"
    q_color, q_bg = quality_colors.get(q, quality_colors["UNKNOWN"])
    quality_icons = {"GOOD": "✅", "POOR": "⚠️", "BLOCKED": "🚫", "UNKNOWN": "❓"}
    q_icon = quality_icons.get(q, "❓")

    return Div(
        # ── header ───────────────────────────────────────────────────────
        Div(
            *([P(result.title, cls="url-result-title")] if result.title else []),
            P(result.url, cls="url-result-source"),
            cls="url-result-header",
        ),
        # ── quality badge ────────────────────────────────────────────────
        Div(
            Span(
                f"{q_icon} Capture quality: {q}",
                style=(
                    f"display:inline-block;padding:0.25rem 0.75rem;"
                    f"border-radius:99px;font-size:0.8rem;font-weight:600;"
                    f"color:{q_color};background:{q_bg};"
                ),
            ),
            P(result.quality_reason,
              style="font-size:0.78rem;color:var(--text-muted);margin-top:0.3rem;"),
            style="margin-bottom:0.75rem;",
        ),
        # ── metrics ──────────────────────────────────────────────────────
        Div(
            Div(
                P("Pages", cls="metric-label"),
                P(str(result.page_count), cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Characters", cls="metric-label"),
                P(f"{result.char_count:,}", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Words", cls="metric-label"),
                P(f"{result.word_count:,}", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Time", cls="metric-label"),
                P(f"{result.processing_time:.1f}s", cls="metric-value"),
                cls="metric-box",
            ),
            cls="metrics-row",
            style="margin-bottom:0.5rem;",
        ),
        # ── token metrics ─────────────────────────────────────────────────
        Div(
            Span(
                f"Tokens in: {result.total_input_tokens:,} · out: {result.total_output_tokens:,}"
                + (f" · saved: {result.tokens_saved:,}" if result.tokens_saved else "")
                + (f" · cached pages: {result.cached_pages}" if result.cached_pages else ""),
                style="font-size:0.75rem;color:var(--text-muted);",
            ),
            style="margin-bottom:0.875rem;",
        ) if result.total_input_tokens else Div(),
        # ── actions ──────────────────────────────────────────────────────
        Div(
            A(
                "⬇ Download .txt",
                href=f"/{txt_filename}",
                download=txt_filename,
                cls="button",
                style="background:var(--purple);",
            ),
            Button(
                "📋 Copy",
                onclick=(
                    f"const btn=this;"
                    f"fetch('/{txt_filename}')"
                    f".then(r=>r.text())"
                    f".then(t=>navigator.clipboard.writeText(t))"
                    f".then(()=>{{"
                    f"btn.textContent='✅ Copied!';btn.style.background='var(--green)';"
                    f"setTimeout(()=>{{btn.textContent='📋 Copy';btn.style.background='';}},2000);}});"
                ),
                cls="button",
            ),
            cls="action-row",
        ),
        # ── preview ───────────────────────────────────────────────────────
        H4("Preview"),
        Pre(file_content, id=preview_id, cls="text-preview"),
        cls="result-area",
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


# ── Chapters ────────────────────────────────────────────────────────────────

def chapters_form_display(chapters, file_hash):
    """Show chapter list with checkboxes and download button, or warning if no TOC."""
    if not chapters:
        return Div(
            H3("Download Chapters"),
            P("This PDF has no table of contents. Chapter download requires a TOC.",
              cls="warning"),
            cls="result-area",
        )

    total_pages = sum(c["end_page"] - c["start_page"] + 1 for c in chapters)

    rows = []
    for ch in chapters:
        pg_count = ch["end_page"] - ch["start_page"] + 1
        rows.append(
            Label(
                Input(type="checkbox", name="chapters", value=str(ch["index"]),
                      checked=True, cls="ch-cb",
                      style="width:1.1rem;height:1.1rem;cursor:pointer;"),
                Span(f'{ch["index"]}.', style="font-weight:600;min-width:1.5rem;"),
                Span(ch["title"], style="flex:1;"),
                Span(f'pp. {ch["start_page"]}–{ch["end_page"]}  ({pg_count} pg)',
                     cls="toc-page"),
                style="display:flex;gap:.5rem;align-items:center;padding:.35rem 0;cursor:pointer;",
            )
        )

    toggle_js = (
        "let cbs=this.closest('form').querySelectorAll('.ch-cb');"
        "let allChecked=[...cbs].every(c=>c.checked);"
        "cbs.forEach(c=>c.checked=!allChecked);"
        "this.textContent=allChecked?'Select All':'Deselect All';"
    )

    return Div(
        H3("Download Chapters"),
        Div(
            Span(f"{len(chapters)} chapters", cls="pill"),
            Span(f"{total_pages} pages total", cls="pill"),
            Span("OCR · one .md per chapter · ZIP", cls="pill"),
            cls="file-meta", style="margin-bottom:.75rem;",
        ),
        Form(
            Div(
                Button("Deselect All", type="button",
                       onclick=toggle_js,
                       cls="button",
                       style="font-size:.78rem;padding:.3rem .7rem;"),
                style="margin-bottom:.5rem;",
            ),
            Div(*rows, style="display:flex;flex-direction:column;gap:0;"),
            Div(
                Button("Download Selected Chapters (OCR)", type="submit",
                       style="background:var(--orange);margin-top:.75rem;"),
                Span(Span(cls="spinner"), " Running OCR on selected chapters…",
                     id="chapters-indicator", cls="htmx-indicator"),
                cls="action-row",
            ),
            hx_post=f"/process/download-chapters/{file_hash}",
            hx_target="#operation-result",
            hx_indicator="#chapters-indicator",
        ),
        cls="result-area",
    )


def chapters_result_display(chapter_results, zip_filename, total_time):
    """Show results after chapter OCR + ZIP creation."""
    total_chapters = len(chapter_results)
    ok_chapters = sum(1 for r in chapter_results if r.get("ok"))
    total_pages = sum(r.get("pages", 0) for r in chapter_results)
    total_input = sum(r.get("input_tokens", 0) for r in chapter_results)
    total_output = sum(r.get("output_tokens", 0) for r in chapter_results)
    total_cached = sum(r.get("cached_count", 0) for r in chapter_results)
    cache_pct = (total_cached / total_pages * 100) if total_pages else 0

    items = []
    for r in chapter_results:
        status = "✅" if r.get("ok") else "❌"
        items.append(
            Li(f'{status} {r["title"]}  —  {r.get("pages", 0)} pg',
               style="font-size:.85rem;")
        )

    return Div(
        H3("Chapters — OCR Complete"),
        Div(
            Span(f"{ok_chapters}/{total_chapters} chapters", cls="pill"),
            Span(f"{total_pages} pages", cls="pill"),
            Span(f"{total_time:.1f}s", cls="pill"),
            Span(f"cache {cache_pct:.0f}%", cls="pill"),
            cls="file-meta", style="margin-bottom:.75rem;",
        ),
        Div(
            Span(f"Tokens — in: {total_input:,}  out: {total_output:,}",
                 style="font-size:.82rem;color:var(--text-muted);"),
        ),
        Ul(*items, style="margin:.75rem 0;"),
        Div(
            A("⬇ Download ZIP",
              href=f"/{zip_filename}",
              download=zip_filename,
              cls="button",
              style="background:var(--orange);"),
            cls="action-row",
        ),
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

    backend   = results.get("backend", "gemini")
    model_id  = results.get("model_id", "")
    gpu       = results.get("gpu", "")
    if backend == "modal":
        badge_text  = f"⚡ Modal · {model_id}" + (f" · {gpu}" if gpu else "")
        badge_color = "#7c3aed"
    else:
        badge_text  = f"☁ Gemini · {model_id}" if model_id else "☁ Gemini"
        badge_color = "#0369a1"
    backend_badge = Div(
        Span(badge_text,
             style=(
                 f"font-size:0.8rem;font-weight:600;color:{badge_color};"
                 f"background:color-mix(in srgb,{badge_color} 12%,transparent);"
                 f"border:1px solid {badge_color};border-radius:999px;"
                 f"padding:0.15rem 0.6rem;"
             )),
        style="margin-bottom:0.75rem;",
    )

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

        backend_badge,

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
