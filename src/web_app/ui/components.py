"""UI components for the web application."""

import json

from fasthtml.common import *
from pdf_utils.config import (
    CAPTURE_JPEG_QUALITY,
    NOTEBOOK_PAGE_BREAK,
    NOTEBOOK_SESSION_MAX_PAGES,
    GCS_ENABLED, GCS_DIRECT_THRESHOLD_BYTES, EFFECTIVE_MAX_UPLOAD_MB,
)


# ── Upload ──────────────────────────────────────────────────────────────────

# Extensions the server accepts. Shared by the file input's `accept` attribute
# and the client-side pre-check, so a drop of the wrong type fails instantly
# instead of after a round trip.
UPLOAD_EXTENSIONS = [
    ".pdf", ".epub", ".jpg", ".jpeg", ".png", ".webp", ".ppt", ".pptx", ".md",
]

_UPLOAD_JS = """
(function () {
  var zone  = document.getElementById('upload-zone');
  var input = document.getElementById('upload-input');
  var err   = document.getElementById('upload-error');
  var out   = document.getElementById('upload-result');
  if (!zone || !input) return;
  var ACCEPT    = __ACCEPT__;
  var GCS       = __GCS__;          // is the direct-to-cloud route available?
  var THRESHOLD = __THRESHOLD__;    // bytes above which we use it
  var MAX_BYTES = __MAX_BYTES__;
  var MAX_LABEL = __MAX_LABEL__;

  function fail(msg) { err.textContent = msg; err.style.display = 'block'; }
  function clearErr() { err.textContent = ''; err.style.display = 'none'; }

  function accepted(file) {
    var name = (file.name || '').toLowerCase();
    var dot  = name.lastIndexOf('.');
    var ext  = dot === -1 ? '' : name.slice(dot);
    if (ACCEPT.indexOf(ext) === -1) {
      fail((ext ? ext + ' files are' : 'That file is') + ' not supported. Accepted: '
           + ACCEPT.join(' '));
      return false;
    }
    if (file.size > MAX_BYTES) {
      fail('That file is ' + (file.size / 1048576).toFixed(0) + ' MB — the limit is '
           + MAX_LABEL + '.');
      return false;
    }
    return true;
  }

  // ── Transport A: plain multipart ──────────────────────────────────────────
  // Hand the file to the existing hidden input so the HTMX change-trigger
  // upload fires unchanged — the same DataTransfer trick the capture page uses.
  function sendMultipart(file) {
    var dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // ── Transport B: direct to cloud storage ──────────────────────────────────
  // Only for files the proxy in front of us would reject. The browser PUTs to a
  // signed URL, then the server pulls the object back down and joins the exact
  // same background-task pipeline the multipart path uses.
  function showProgress(phase, pct) {
    out.innerHTML =
      '<div class="upload-progress">' +
        '<div class="progress-phase"><span class="spinner"></span><span></span></div>' +
        '<div class="progress-track"><div class="progress-fill"></div></div>' +
      '</div>';
    setProgress(phase, pct);
  }
  function setProgress(phase, pct) {
    var label = out.querySelector('.progress-phase span:last-child');
    var fill  = out.querySelector('.progress-fill');
    if (label) label.textContent = phase;
    if (fill)  fill.style.width = pct + '%';
  }
  function abort(msg) {
    out.innerHTML = '';
    fail(msg);
  }

  function sendDirect(file) {
    showProgress('Preparing upload…', 2);
    fetch('/api/request-upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        size: file.size,
        content_type: file.type || 'application/octet-stream'
      })
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.signed_url) throw new Error(data.error || 'no upload URL returned');

      var xhr = new XMLHttpRequest();
      xhr.open('PUT', data.signed_url, true);
      xhr.setRequestHeader('Content-Type', data.content_type);
      // Cap the PUT's share of the bar at 85% — the server still has to fetch
      // the object back and process it after this finishes.
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
          setProgress('Uploading to cloud storage…',
                      Math.round(e.loaded / e.total * 85));
        }
      };
      xhr.onerror = function () { abort('Network error while uploading.'); };
      xhr.onload = function () {
        if (xhr.status < 200 || xhr.status >= 300) {
          abort('Cloud upload failed (HTTP ' + xhr.status + ').');
          return;
        }
        setProgress('Handing off to server…', 88);
        fetch('/api/confirm-upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            gcs_object_name: data.gcs_object_name,
            original_filename: file.name
          })
        })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          // The reply is a polling fragment; htmx only wires up hx-* attributes
          // on nodes it knows about, and innerHTML is invisible to it.
          out.innerHTML = html;
          if (window.htmx) window.htmx.process(out);
        })
        .catch(function (e) { abort('Server error: ' + e.message); });
      };
      xhr.send(file);
    })
    .catch(function (e) { abort('Could not start upload: ' + e.message); });
  }

  // Every entry point (file picker, drop, paste) ends up assigning to the
  // hidden input, so routing and validation live in one place: the htmx hook
  // below, which fires no matter how the file got there.
  function send(file) {
    if (!file) return;
    sendMultipart(file);
  }

  input.addEventListener('htmx:beforeRequest', function (e) {
    var file = input.files && input.files[0];
    if (!file) return;
    if (!accepted(file)) { e.preventDefault(); return; }
    clearErr();
    if (GCS && file.size > THRESHOLD) {
      e.preventDefault();   // too big for the proxy — take the cloud route
      sendDirect(file);
    }
  });

  // Whole card opens the dialog. The guard stops the programmatic input.click()
  // from bubbling back into this handler.
  zone.addEventListener('click', function (e) {
    if (e.target.closest('#upload-input, .file-label-btn')) return;
    input.click();
  });

  ['dragenter', 'dragover'].forEach(function (ev) {
    zone.addEventListener(ev, function (e) {
      e.preventDefault(); e.stopPropagation();
      zone.classList.add('upload-zone-drag');
    });
  });
  zone.addEventListener('dragleave', function (e) {
    // Moving over a child fires dragleave on the parent — ignore those.
    if (zone.contains(e.relatedTarget)) return;
    zone.classList.remove('upload-zone-drag');
  });
  zone.addEventListener('drop', function (e) {
    e.preventDefault(); e.stopPropagation();
    zone.classList.remove('upload-zone-drag');
    send(e.dataTransfer && e.dataTransfer.files[0]);
  });

  // Without this, a file dropped just outside the zone navigates the tab to it.
  ['dragover', 'drop'].forEach(function (ev) {
    window.addEventListener(ev, function (e) {
      if (!zone.contains(e.target)) e.preventDefault();
    });
  });

  document.addEventListener('paste', function (e) {
    var f = e.clipboardData && e.clipboardData.files && e.clipboardData.files[0];
    if (f) { e.preventDefault(); send(f); }
  });
})();
"""


def upload_form():
    """Upload zone: click anywhere, drop a file on it, or paste one.

    HTMX listens for `change` on the hidden file input and posts as
    multipart/form-data; drag-drop and paste both route through that same input
    so there is exactly one upload path.

    When GCS is configured, files over GCS_DIRECT_THRESHOLD_BYTES take a second
    transport instead: the browser PUTs them straight to a signed bucket URL,
    because anything bigger than that is rejected by the proxy in front of the
    app before the request ever reaches it. Both transports converge on the same
    background task and the same progress UI.
    """
    return Div(
        Form(
            # ── Upload card ───────────────────────────────────────────────
            Div(
                P("📁", cls="upload-icon"),
                Input(
                    type="file",
                    name="file",
                    id="upload-input",
                    accept=",".join(UPLOAD_EXTENSIONS),
                    style="display:none",
                    hx_post="/upload",
                    hx_encoding="multipart/form-data",
                    hx_trigger="change",
                    hx_target="#upload-result",
                    hx_swap="innerHTML",
                    hx_indicator="#upload-indicator",
                ),
                # Styled label acts as the visible "Choose File" button
                Label("Choose File", cls="file-label-btn",
                      **{"for": "upload-input"}),
                P("or drop a file here · or paste one",
                  cls="upload-hint"),
                P(f"PDF · EPUB · PPT · MD · JPG · PNG · WEBP  ·  max {EFFECTIVE_MAX_UPLOAD_MB} MB",
                  cls="upload-hint"),
                P("", id="upload-error", cls="upload-error"),
                id="upload-zone",
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
        Script(
            _UPLOAD_JS
            .replace("__ACCEPT__",    json.dumps(UPLOAD_EXTENSIONS))
            .replace("__GCS__",       json.dumps(GCS_ENABLED))
            .replace("__THRESHOLD__", json.dumps(GCS_DIRECT_THRESHOLD_BYTES))
            .replace("__MAX_BYTES__", json.dumps(EFFECTIVE_MAX_UPLOAD_MB * 1024 * 1024))
            .replace("__MAX_LABEL__", json.dumps(f"{EFFECTIVE_MAX_UPLOAD_MB} MB"))
        ),
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


def auto_download_script(stored_filename: str, download_as: str):
    """Forces an immediate browser download of a just-saved upload,
    via a synthetic <a download> click (window.location.href would just
    open PDFs in-browser instead of downloading them)."""
    return Script(
        "(function(){"
        "var a=document.createElement('a');"
        f"a.href='/{stored_filename}';"
        f"a.download='{download_as}';"
        "document.body.appendChild(a);a.click();a.remove();"
        "})();"
    )


def task_progress_poll(task_id: str, status_url: str, label: str,
                       pct: int = 0, interval: str = "750ms"):
    """Self-replacing progress container for a background job.

    Polls slower than the upload flow's 250 ms: these jobs run for minutes, and
    the final swap carries no polling attributes so the loop ends on its own.
    """
    return Div(
        _progress_bar(label, pct),
        id=f"poll-{task_id}",
        hx_get=status_url,
        hx_trigger=f"every {interval}",
        hx_target="this",
        hx_swap="outerHTML",
    )


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
    ft = file_info.file_type
    if ft == "pdf":
        icon, label = "📄", "PDF"
    elif ft == "epub":
        icon, label = "📖", "EPUB"
    else:
        icon, label = "🖼", "Image"
    size = f"{file_info.file_size / 1024 / 1024:.1f} MB"

    pills = [
        Span(f"{icon} {label}", cls="pill"),
        Span(size, cls="pill"),
    ]
    if ft == "pdf":
        pills.append(Span(f"{file_info.page_count} pages", cls="pill"))
    elif ft == "epub":
        pills.append(Span(f"{file_info.page_count} chapters", cls="pill"))

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
    """Responsive CSS-grid of operation buttons with icon + label.

    Ops-grid buttons load into `#operation-form`; the forms they load submit
    into `#operation-result` below. That way a form survives its own result —
    changing a page range and rerunning no longer means re-opening the form.
    """
    if file_type == "image":
        ops = [
            _op_btn("🤖", "OCR",
                    hx_get=f"/extract-text-llm-image/{file_hash}",
                    hx_target="#operation-form",
                    extra_cls="purple"),
        ]
    elif file_type == "epub":
        ops = [
            _op_btn("ℹ️", "Metadata",
                    hx_get=f"/epub-metadata/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("📑", "TOC",
                    hx_post=f"/process/epub-toc/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("📝", "Text",
                    hx_get=f"/epub-text-form/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("🎨", "Images",
                    hx_get=f"/epub-images-form/{file_hash}",
                    hx_target="#operation-form",
                    extra_cls="green"),
            _op_btn("📚", "Chapters",
                    hx_get=f"/epub-chapters-form/{file_hash}",
                    hx_target="#operation-form",
                    extra_cls="orange"),
        ]
    else:
        ops = [
            _op_btn("🤖", "OCR",
                    hx_get=f"/extract-text-llm-form/{file_hash}",
                    hx_target="#operation-form",
                    extra_cls="purple"),
            _op_btn("📑", "TOC",
                    hx_post=f"/process/toc/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("✂️", "Extract Pages",
                    hx_get=f"/extract-pages-form/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("🖼", "To Images",
                    hx_get=f"/convert-images-form/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("📝", "Text",
                    hx_get=f"/extract-text-form/{file_hash}",
                    hx_target="#operation-form"),
            _op_btn("🎨", "Images",
                    hx_get=f"/extract-images-form/{file_hash}",
                    hx_target="#operation-form",
                    extra_cls="green"),
            _op_btn("📚", "Chapters",
                    hx_get=f"/download-chapters-form/{file_hash}",
                    hx_target="#operation-form",
                    extra_cls="orange"),
        ]

    return Div(
        H3("Operations"),
        # Switching operations drops the previous operation's result, so a stale
        # result never sits under an unrelated form. htmx events bubble, so one
        # handler on the grid covers every button in it.
        Div(*ops, cls="ops-grid",
            **{"hx-on::before-request":
               "document.getElementById('operation-result').innerHTML=''"}),
        Div(id="operation-form"),
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


# ── PDF from a direct link ───────────────────────────────────────────────────

def pdf_url_form():
    """Paste a link that ends in .pdf; the server downloads it for you.

    Deliberately its own box rather than a third button on the URL card: those
    two extract *text from a web page*, while this one produces an uploaded
    file, lands in `#pdf-url-result`, and unlocks the whole PDF toolset. Sharing
    the card would put two different kinds of outcome behind adjacent buttons.

    Same htmx caveat as url_input_form(): htmx cancels the native submit for a
    button inside a form, taking the validation bubble with it, so the guard
    calls reportValidity() itself.
    """
    validate_guard = (
        "if(!this.form.reportValidity()){"
        "event.preventDefault();event.stopImmediatePropagation();}"
    )

    return Div(
        Div(
            Div(cls="or-line"),
            Span("or fetch a PDF link", cls="or-label"),
            Div(cls="or-line"),
            cls="or-divider",
        ),
        Div(
            Div(
                Span("📄", cls="url-section-icon"),
                Div(
                    P("PDF from a link", cls="url-section-title"),
                    P("For URLs that point straight at a PDF file. The server "
                      "downloads it, then every PDF operation works on it as if "
                      "you had uploaded the file yourself.",
                      cls="url-section-sub"),
                    cls="url-section-text",
                ),
                cls="url-section-header",
            ),
            Form(
                Input(
                    type="url",
                    name="url",
                    placeholder="https://example.com/paper.pdf",
                    autocomplete="off",
                    required=True,
                    style="margin-bottom:0.5rem;",
                ),
                Div(
                    Button(
                        "⬇️ Fetch PDF",
                        type="submit",
                        onclick=validate_guard,
                        hx_post="/process/pdf-from-url",
                        hx_include="closest form",
                        hx_target="#pdf-url-result",
                        hx_swap="innerHTML",
                        hx_indicator="#pdf-url-indicator",
                        style="justify-content:center;",
                    ),
                    cls="url-actions",
                ),
                Div(
                    Span(f"Downloads up to {EFFECTIVE_MAX_UPLOAD_MB} MB",
                         style="font-size:0.75rem;color:var(--text-muted);"),
                    Div(
                        Span(cls="spinner"),
                        Span("Fetching…"),
                        id="pdf-url-indicator",
                        cls="htmx-indicator",
                        style="color:var(--primary);font-size:0.8rem;font-weight:500;gap:0.35rem;",
                    ),
                    cls="url-options",
                ),
            ),
            cls="url-card",
        ),
        Div(id="pdf-url-result"),
    )


# ── URL to Markdown ──────────────────────────────────────────────────────────

def url_input_form():
    """One URL input, two ways to extract it.

    Both buttons post the same form to different routes via button-level
    `hx-post`, so the method is chosen *after* pasting rather than before.
    htmx cancels the native submit for buttons inside a form, which also
    suppresses the browser's validation bubble — the onclick guard calls
    reportValidity() itself and stops htmx's own handler when it fails.
    """
    validate_guard = (
        "if(!this.form.reportValidity()){"
        "event.preventDefault();event.stopImmediatePropagation();}"
    )

    return Div(
        # ── divider ──────────────────────────────────────────────────────
        Div(
            Div(cls="or-line"),
            Span("or extract from a URL", cls="or-label"),
            Div(cls="or-line"),
            cls="or-divider",
        ),
        Div(
            Div(
                Span("🔗", cls="url-section-icon"),
                Div(
                    P("Extract from URL", cls="url-section-title"),
                    P("Markdown — trafilatura, fast, clean for articles. "
                      "Browser + OCR — renders in headless Chrome, then AI OCR; "
                      "handles JS, cookie banners & pop-ups.",
                      cls="url-section-sub"),
                    cls="url-section-text",
                ),
                cls="url-section-header",
            ),
            Form(
                Input(
                    type="url",
                    name="url",
                    placeholder="https://example.com/article",
                    autocomplete="off",
                    required=True,
                    style="margin-bottom:0.5rem;",
                ),
                Div(
                    Button(
                        "⚡ Markdown — fast",
                        type="submit",
                        onclick=validate_guard,
                        hx_post="/process/url-to-markdown",
                        hx_include="closest form",
                        hx_target="#url-result",
                        hx_swap="innerHTML",
                        hx_indicator="#url-indicator",
                        style="justify-content:center;",
                    ),
                    Button(
                        "🖨️ Browser + OCR — thorough",
                        type="submit",
                        onclick=validate_guard,
                        hx_post="/process/url-to-pdf-ocr",
                        hx_include="closest form",
                        hx_target="#url-result",
                        hx_swap="innerHTML",
                        hx_indicator="#url-pdf-indicator",
                        style="justify-content:center;background:var(--purple);",
                    ),
                    cls="url-actions",
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
                    Span("(Markdown mode only)",
                         style="font-size:0.75rem;color:var(--text-muted);"),
                    Div(
                        Span(cls="spinner"),
                        Span("Fetching…"),
                        id="url-indicator",
                        cls="htmx-indicator",
                        style="color:var(--primary);font-size:0.8rem;font-weight:500;gap:0.35rem;",
                    ),
                    Div(
                        Span(cls="spinner"),
                        Span("Rendering page…"),
                        id="url-pdf-indicator",
                        cls="htmx-indicator",
                        style="color:var(--purple);font-size:0.8rem;font-weight:500;gap:0.35rem;",
                    ),
                    cls="url-options",
                ),
            ),
            cls="url-card",
        ),
        Div(id="url-result"),
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
                href=f"/download/url-md/{md_filename}",
                download=md_filename,
                cls="button",
                style="background:var(--green);",
            ),
            Button(
                "📋 Copy",
                onclick=(
                    f"fetch('/download/url-md/{md_filename}').then(r=>r.text()).then(t=>{{"
                    f"navigator.clipboard.writeText(t).then(()=>{{"
                    f"this.textContent='✅ Copied!';this.style.background='var(--green)';"
                    f"setTimeout(()=>{{this.textContent='📋 Copy';this.style.background='';}},2000);}});}});"
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
        # ── quality badge (stays visible — it qualifies the text below) ──
        Div(
            Span(
                f"{q_icon} Capture quality: {q}",
                style=(
                    f"display:inline-block;padding:0.25rem 0.75rem;"
                    f"border-radius:99px;font-size:0.8rem;font-weight:600;"
                    f"color:{q_color};background:{q_bg};"
                ),
            ),
            style="margin-bottom:0.75rem;",
        ),
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
            Span(f"{result.char_count:,} characters", cls="pill",
                 style="align-self:center;"),
            cls="action-row",
        ),
        # ── preview ───────────────────────────────────────────────────────
        H4("Preview"),
        Pre(file_content, id=preview_id, cls="text-preview"),
        # ── diagnostics, on demand ───────────────────────────────────────
        Details(
            Summary(
                f"Details — {result.page_count} pages · {result.word_count:,} words"
                f" · {result.processing_time:.1f}s",
                cls="details-summary",
            ),
            P(result.quality_reason,
              style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.5rem;"),
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
            *([Span(
                f"Tokens in: {result.total_input_tokens:,} · out: {result.total_output_tokens:,}"
                + (f" · saved: {result.tokens_saved:,}" if result.tokens_saved else "")
                + (f" · cached pages: {result.cached_pages}" if result.cached_pages else ""),
                style="font-size:0.75rem;color:var(--text-muted);",
            )] if result.total_input_tokens else []),
        ),
        cls="result-area",
    )


# ── TOC ──────────────────────────────────────────────────────────────────────

def toc_display(toc, file_hash: str = None, chapters=None):
    """Table of contents, with the two things you usually want next.

    `chapters` are the page ranges `compute_chapter_ranges` derives from this
    same TOC — passing them in lets each top-level entry carry a concrete
    "OCR pp. 12–34" button instead of the user re-deriving the range by hand.
    """
    if not toc:
        return Div(
            H3("Table of Contents"),
            P("This PDF has no table of contents.", cls="warning"),
            cls="result-area",
        )

    # Top-level entries are matched to their chapter range by title + page.
    ranges = {(c["title"], c["start_page"]): c for c in (chapters or [])}

    items = []
    for level, title, page in toc:
        level_cls = f"toc-l{min(level, 3)}"
        bold = "font-weight:700;" if level == 0 else ""
        ch = ranges.get((title, page)) if file_hash else None
        items.append(
            Li(
                Span(title, cls="toc-title"),
                *([Button(
                    f'OCR pp. {ch["start_page"]}–{ch["end_page"]}',
                    cls="toc-ocr-btn",
                    hx_post=f"/process/extract-text-llm/{file_hash}",
                    hx_vals=f'{{"start_page": {ch["start_page"]}, '
                            f'"end_page": {ch["end_page"]}}}',
                    hx_target="#operation-result",
                )] if ch else []),
                Span(f"p. {page}", cls="toc-page"),
                cls=f"toc-item {level_cls}",
                style=bold,
            )
        )

    return Div(
        H3("Table of Contents"),
        *([Div(
            Button(
                "📚 Download as chapters",
                hx_get=f"/download-chapters-form/{file_hash}",
                hx_target="#operation-form",
                style="background:var(--orange);",
            ),
            cls="action-row",
            style="margin-top:0;",
        )] if file_hash else []),
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

    # One-line summary of everything hidden behind the disclosure.
    summary_bits = [f"{proc_time:.1f}s", f"{cache_rate:.0f}% cached"]
    if in_tok or out_tok:
        summary_bits.append(f"{in_tok:,} tok in")
        summary_bits.append(f"{out_tok:,} tok out")
    details_summary = "Details — " + " · ".join(summary_bits)

    failed = results.get("failed_pages", [])

    return Div(
        P(results.get("summary", "OCR complete"),
          cls="alert-success"),

        # Failures stay outside the collapse — a silently hidden failure is worse
        # than the telemetry noise this section exists to bury.
        *([P(f"⚠ {len(failed)} page(s) failed: "
             + ", ".join(str(p) for p in failed[:20])
             + ("…" if len(failed) > 20 else ""),
            cls="alert-warning")]
          if failed else []),

        # ── what the user actually came for ────────────────────────────────
        Div(
            A("⬇ Download Text",
              href=f"/{text_filename}",
              download=text_filename,
              cls="button",
              style="background:var(--green);"),
            Button(
                "📋 Copy",
                # Fetched from the download route rather than read off the preview
                # element: the DOM copy silently truncates long transcriptions.
                onclick=(
                    f"const btn=this;"
                    f"fetch('/{text_filename}')"
                    f".then(r=>r.text())"
                    f".then(t=>navigator.clipboard.writeText(t))"
                    f".then(()=>{{"
                    f"btn.textContent='✅ Copied!';btn.style.background='var(--green)';"
                    f"setTimeout(()=>{{btn.textContent='📋 Copy';btn.style.background='';}},2000);}});"
                ),
                cls="button",
            ),
            Span(f"{len(results['full_text']):,} characters", cls="pill",
                 style="align-self:center;"),
            cls="action-row",
        ),

        H4("Preview"),
        Pre(results["full_text"],
            id=preview_id,
            cls="text-preview"),

        # ── telemetry, on demand ───────────────────────────────────────────
        Details(
            Summary(details_summary, cls="details-summary"),
            metrics,
            H4("Per-page detail"),
            Ul(*page_items, cls="page-detail-list"),
        ),

        cls="result-area",
    )


# ── EPUB image gallery ────────────────────────────────────────────────────────

def epub_image_gallery(images_data: dict, file_hash: str):
    """Gallery of images extracted from an EPUB (no page grouping)."""
    if not images_data:
        return Div(
            H3("No Images Found"),
            P("No embedded images found in this EPUB.", cls="warning"),
            cls="result-area",
        )

    all_images = [img for group in images_data.values() for img in group]
    total = len(all_images)

    image_items = [
        Div(
            A(
                Img(src=img["data"], alt=img["filename"], cls="image-thumbnail"),
                href=img["data"],
                download=img["filename"],
                title=f"Download {img['filename']}",
            ),
            cls="image-item",
        )
        for img in all_images
    ]

    return Div(
        H3("Extracted Images"),
        Div(
            Span(f"{total} image{'s' if total != 1 else ''}", cls="pill"),
            cls="file-meta", style="margin-bottom:0.75rem;",
        ),
        P("Click any image to download it",
          style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;"),
        Div(
            Button(
                "⬇ Download All as ZIP",
                onclick=(
                    f"this.textContent='Preparing…';this.disabled=true;"
                    f"window.location.href='/epub-download-image-zip/{file_hash}';"
                    f"setTimeout(()=>{{this.textContent='⬇ Download All as ZIP';this.disabled=false;}},2000);"
                ),
                cls="button",
            ),
            cls="action-row",
        ),
        Div(*image_items, cls="image-extraction-grid"),
        cls="result-area",
    )


# ── Camera capture (handwriting OCR) ────────────────────────────────────────

_CAPTURE_JS = """
(function () {
  var video   = document.getElementById('cap-video');
  var canvas  = document.getElementById('cap-canvas');
  var status  = document.getElementById('cap-status');
  var strip   = document.getElementById('cap-pages');
  var result  = document.getElementById('capture-result');
  var shoot   = document.getElementById('cap-shoot');
  var retake  = document.getElementById('cap-retake');
  var nextBtn = document.getElementById('cap-next');
  var doneBtn = document.getElementById('cap-done');
  var stream  = null;
  var cameraReady = false;
  var currentBlob = null;
  var posting = false;
  var waiting = false;
  var pollTimer = null;
  var pages = [];
  var MAX_PAGES = __MAX_PAGES__;
  var PAGE_BREAK = __PAGE_BREAK__;

  function say(msg, isError) {
    status.textContent = msg;
    status.className = isError ? 'cap-status cap-status-error' : 'cap-status';
  }

  function stop() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
  }

  function resumeLive() {
    currentBlob = null;
    canvas.style.display = 'none';
    video.style.display  = 'block';
    syncButtons();
  }

  function atLimit() {
    return pages.length >= MAX_PAGES;
  }

  function syncButtons() {
    var frozen = !!currentBlob;
    var hasPages = pages.length > 0;
    var busy = posting || waiting;

    shoot.style.display = frozen ? 'none' : 'inline-flex';
    shoot.disabled = busy || !cameraReady || atLimit();

    retake.style.display = frozen ? 'inline-flex' : 'none';
    retake.disabled = busy;

    nextBtn.style.display = frozen && !atLimit() ? 'inline-flex' : 'none';
    nextBtn.disabled = busy;

    // Frozen: this freeze can be the last page. Live + existing pages: finish
    // without another capture (Next on the last page is not a dead end).
    doneBtn.style.display = (frozen || hasPages) ? 'inline-flex' : 'none';
    doneBtn.disabled = busy || (!frozen && !hasPages);
  }

  function renderStrip() {
    if (!pages.length) {
      strip.innerHTML = '';
      strip.hidden = true;
      return;
    }
    strip.hidden = false;
    strip.innerHTML = '';
    pages.forEach(function (p) {
      var chip = document.createElement('div');
      chip.className = 'cap-page-chip is-' + p.status;
      var img = document.createElement('img');
      img.src = p.thumb;
      img.alt = 'Page ' + p.n;
      var num = document.createElement('span');
      num.className = 'cap-page-chip-num';
      num.textContent = String(p.n);
      var st = document.createElement('span');
      st.className = 'cap-page-chip-state';
      if (p.status === 'done') st.textContent = '✓';
      else if (p.status === 'error' || p.status === 'expired') st.textContent = '!';
      else st.textContent = '…';
      chip.appendChild(img);
      chip.appendChild(num);
      chip.appendChild(st);
      strip.appendChild(chip);
    });
  }

  function refreshPageStatuses() {
    var pending = pages.filter(function (p) { return p.status === 'pending'; });
    if (!pending.length) {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      return;
    }
    pending.forEach(function (p) {
      fetch('/notebook-page-status/' + p.taskId)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status && data.status !== p.status) {
            p.status = data.status;
            if (data.error) p.error = data.error;
            renderStrip();
          }
        })
        .catch(function () { /* next tick retries */ });
    });
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(refreshPageStatuses, 1000);
    refreshPageStatuses();
  }

  function waitingHtml(done, total) {
    var pct = total ? Math.round((done / total) * 95) : 10;
    return '<div class="upload-progress">'
      + '<div class="progress-phase"><span class="spinner"></span>'
      + '<span>Transcribing ' + done + ' of ' + total + ' pages…</span></div>'
      + '<div class="progress-track"><div class="progress-fill" style="width:'
      + pct + '%"></div></div></div>';
  }

  function showSessionResult() {
    var ids = pages.map(function (p) { return p.taskId; }).join(',');
    fetch('/notebook-session-result?ids=' + encodeURIComponent(ids))
      .then(function (r) { return r.text(); })
      .then(function (html) {
        result.innerHTML = html;
        waiting = false;
        syncButtons();
      })
      .catch(function (err) {
        result.innerHTML = '';
        say('Could not load the transcription: ' + err, true);
        waiting = false;
        syncButtons();
      });
  }

  function waitForAll() {
    waiting = true;
    syncButtons();
    var ids = pages.map(function (p) { return p.taskId; }).join(',');
    function tick() {
      fetch('/notebook-session-status?ids=' + encodeURIComponent(ids))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.status === 'pending') {
            result.innerHTML = waitingHtml(data.done, data.total);
            setTimeout(tick, 750);
            return;
          }
          if (data.error) {
            say(data.error, true);
            waiting = false;
            syncButtons();
            return;
          }
          showSessionResult();
        })
        .catch(function (err) {
          say('Could not check transcription status: ' + err, true);
          waiting = false;
          syncButtons();
        });
    }
    result.innerHTML = waitingHtml(0, pages.length);
    tick();
  }

  function acceptFrame() {
    if (!currentBlob || posting) return Promise.resolve(false);
    if (atLimit()) {
      say('That is the limit (' + MAX_PAGES + ' pages). Press Done.', true);
      return Promise.resolve(false);
    }
    posting = true;
    var blob = currentBlob;
    currentBlob = null;
    var thumb = canvas.toDataURL('image/jpeg', 0.45);
    syncButtons();
    var fd = new FormData();
    fd.append('frame', blob, 'capture.jpg');
    return fetch('/process/notebook-page', { method: 'POST', body: fd })
      .then(function (r) { return r.json().then(function (data) { return { okHttp: r.ok, data: data }; }); })
      .then(function (res) {
        posting = false;
        if (!res.data || !res.data.ok) {
          currentBlob = blob;
          say((res.data && res.data.error) || 'Could not send the page.', true);
          syncButtons();
          return false;
        }
        pages.push({
          taskId: res.data.task_id,
          n: pages.length + 1,
          thumb: thumb,
          status: 'pending'
        });
        renderStrip();
        startPolling();
        syncButtons();
        return true;
      })
      .catch(function (err) {
        posting = false;
        currentBlob = blob;
        say('Could not send the page: ' + err, true);
        syncButtons();
        return false;
      });
  }

  function start() {
    if (!window.isSecureContext) {
      say('Camera needs HTTPS or localhost. This page was loaded over an insecure '
          + 'connection, so the browser will not grant camera access.', true);
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      say('This browser does not support camera capture.', true);
      return;
    }
    say('Starting camera…');
    // Ask for the highest resolution the device will give us; browsers clamp to the
    // nearest supported mode rather than failing. Handwriting needs the pixels.
    navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: 'environment' },
        width:  { ideal: 3840 },
        height: { ideal: 2160 }
      },
      audio: false
    }).then(function (s) {
      stream = s;
      video.srcObject = s;
      return video.play();
    }).then(function () {
      var t = stream.getVideoTracks()[0];
      var st = t.getSettings ? t.getSettings() : {};
      cameraReady = true;
      syncButtons();
      say('Camera ready — ' + (st.width || video.videoWidth) + '×'
          + (st.height || video.videoHeight)
          + '. Fill the frame, capture, then Next page. Press Done after the last page.');
    }).catch(function (err) {
      cameraReady = false;
      syncButtons();
      if (err && (err.name === 'NotAllowedError' || err.name === 'SecurityError')) {
        say('Camera permission was denied. Allow camera access for this site in your '
            + 'browser settings, then reload this page.', true);
      } else if (err && (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError')) {
        say('No camera was found on this device.', true);
      } else if (err && err.name === 'NotReadableError') {
        say('The camera is in use by another application. Close it and reload.', true);
      } else {
        say('Could not start the camera: ' + (err && err.name ? err.name : err), true);
      }
    });
  }

  shoot.addEventListener('click', function () {
    if (!video.videoWidth) { say('Camera is still starting up — try again.', true); return; }
    if (atLimit()) {
      say('That is the limit (' + MAX_PAGES + ' pages). Press Done.', true);
      return;
    }
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function (blob) {
      if (!blob) { say('Could not read the frame. Try again.', true); return; }
      currentBlob = blob;
      canvas.style.display = 'block';
      video.style.display  = 'none';
      syncButtons();
      say('Captured at ' + canvas.width + '×' + canvas.height + ' ('
          + Math.round(blob.size / 1024) + ' KB). Readable? Next page, Done, or retake.');
    }, 'image/jpeg', __QUALITY__);
  });

  retake.addEventListener('click', function () {
    resumeLive();
    say('Retaking — line up the page and capture again.');
  });

  nextBtn.addEventListener('click', function () {
    if (posting || waiting || !currentBlob) return;
    acceptFrame().then(function (ok) {
      if (!ok) return;
      resumeLive();
      var n = pages.length;
      say('Page ' + n + ' is transcribing. Line up the next page and capture.');
    });
  });

  // Result HTML is injected later; keep this on window so the Copy buttons
  // can call it without stuffing JS into an onclick attribute.
  window.copyCapText = function (btn, onlyId) {
    var nodes = onlyId
      ? [document.getElementById(onlyId)]
      : document.querySelectorAll('.cap-textarea');
    var parts = [];
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i]) parts.push(nodes[i].value);
    }
    var prev = btn.textContent;
    navigator.clipboard.writeText(parts.join('\\n' + PAGE_BREAK + '\\n')).then(function () {
      btn.textContent = '✅ Copied!';
      btn.style.background = 'var(--green)';
      setTimeout(function () {
        btn.textContent = prev;
        btn.style.background = '';
      }, 2000);
    }).catch(function (err) {
      say('Could not copy: ' + (err && err.message ? err.message : err), true);
    });
  };

  doneBtn.addEventListener('click', function () {
    if (posting || waiting) return;
    waiting = true;
    syncButtons();
    var pending = currentBlob ? acceptFrame() : Promise.resolve(true);
    pending.then(function (ok) {
      if (!ok) { waiting = false; syncButtons(); return; }
      if (!pages.length) {
        waiting = false;
        syncButtons();
        say('Capture a page first.', true);
        return;
      }
      resumeLive();
      say(pages.length === 1
        ? 'Transcribing the page…'
        : 'Finishing ' + pages.length + ' pages…');
      waitForAll();
    });
  });

  // Release the camera so the hardware indicator light goes out.
  window.addEventListener('pagehide', stop);
  syncButtons();
  start();
})();
"""


def capture_card():
    """Index-page link to the camera capture page.

    Deliberately a link, not an inline camera: embedding a live preview on the index
    would prompt for camera permission on every visit to the app. One row rather
    than a full card so the whole index still fits one desktop viewport.
    """
    return A(
        Span("📷", cls="capture-link-icon"),
        Span("Notebook to Text", style="font-weight:600;"),
        Span("transcribe one or more notebook pages with your camera",
             cls="capture-link-sub"),
        Span("→", style="margin-left:auto;color:var(--text-muted);"),
        href="/capture",
        cls="capture-link",
    )


def capture_page():
    """Full camera capture page: live preview, multi-page session, transcribe."""
    js = (
        _CAPTURE_JS
        .replace("__QUALITY__", str(CAPTURE_JPEG_QUALITY))
        .replace("__MAX_PAGES__", str(NOTEBOOK_SESSION_MAX_PAGES))
        .replace("__PAGE_BREAK__", json.dumps(NOTEBOOK_PAGE_BREAK))
    )
    return Titled(
        "Notebook to Text",
        Div(
            A("← Back", href="/", cls="logout-link"),
            P("Capture each page as you go. Transcription starts when you accept "
              "a page, so you only wait after Done. An open two-page spread still "
              "counts as one capture.",
              cls="page-subtitle"),
            Div(
                Video(
                    id="cap-video",
                    autoplay=True,
                    playsinline=True,
                    muted=True,
                    cls="cap-media",
                ),
                Canvas(id="cap-canvas", cls="cap-media", style="display:none;"),
                Div(id="cap-pages", cls="cap-pages", hidden=True),
                P("Starting camera…", id="cap-status", cls="cap-status"),
                Div(
                    Button("📷 Capture", type="button", id="cap-shoot",
                           disabled=True, cls="button"),
                    Button("↺ Retake", type="button", id="cap-retake",
                           cls="button",
                           style="display:none;background:var(--orange);"),
                    Button("Next page", type="button", id="cap-next",
                           cls="button", style="display:none;"),
                    Button("Done", type="button", id="cap-done",
                           cls="button",
                           style="display:none;background:var(--green);"),
                    cls="action-row",
                ),
                cls="url-card",
            ),
            Div(id="capture-result"),
            Script(js),
            cls="app-wrap",
        ),
    )


def notebook_session_result(pages):
    """Editable transcriptions for every accepted camera frame, plus Copy all.

    `pages` is the list produced by `collect_notebook_pages` once every task is
    terminal. Copy reads the textareas so manual fixes survive.
    """
    ok_pages = [p for p in pages if p.get("ok")]
    all_text = "\n".join(p.get("full_text") or "" for p in ok_pages)
    in_tok = sum(p.get("total_input_tokens") or 0 for p in ok_pages)
    out_tok = sum(p.get("total_output_tokens") or 0 for p in ok_pages)
    times = [p.get("processing_time") or 0 for p in ok_pages]
    wall = max(times) if times else 0
    multi = len(pages) > 1
    copy_label = "📋 Copy all" if multi else "📋 Copy"

    page_blocks = []
    for p in pages:
        n = p.get("n")
        textarea_id = "cap-text" if not multi and n == 1 else f"cap-text-{n}"
        head_bits = [Span(f"Page {n}", cls="cap-page-result-title")]
        if not p.get("ok"):
            head_bits.append(
                Span(p.get("error") or "Transcription failed.", cls="cap-page-error")
            )
        elif multi:
            head_bits.append(
                Button(
                    "📋 Copy",
                    type="button",
                    onclick=f"copyCapText(this,{json.dumps(textarea_id)})",
                    cls="button cap-page-copy",
                )
            )
        page_blocks.append(
            Div(
                Div(*head_bits, cls="cap-page-result-head"),
                Textarea(
                    p.get("full_text") or "",
                    id=textarea_id,
                    cls="cap-textarea",
                    spellcheck="false",
                ),
                cls="cap-page-result" + ("" if multi else " cap-page-result-solo"),
            )
        )

    return Div(
        Div(
            Div(
                P("Pages", cls="metric-label"),
                P(f"{len(pages)}", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Characters", cls="metric-label"),
                P(f"{len(all_text):,}", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Words", cls="metric-label"),
                P(f"{len(all_text.split()) if all_text.strip() else 0:,}",
                  cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Time", cls="metric-label"),
                P(f"{wall:.1f}s", cls="metric-value"),
                cls="metric-box",
            ),
            Div(
                P("Tokens", cls="metric-label"),
                P(f"{in_tok + out_tok:,}", cls="metric-value"),
                cls="metric-box",
            ),
            cls="metrics-row",
            style="margin-bottom:0.5rem;",
        ),
        Div(
            Button(
                copy_label,
                type="button",
                onclick="copyCapText(this)",
                cls="button",
            ),
            cls="action-row",
        ),
        P("Editable — fix any misreadings before copying. Uncertain words are marked [?].",
          style="font-size:0.78rem;color:var(--text-muted);margin-bottom:0.35rem;"),
        *page_blocks,
        cls="result-area",
    )
