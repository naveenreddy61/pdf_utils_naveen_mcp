"""EPUB processing routes."""

import io
import time
from pathlib import Path
from fasthtml.common import *
from starlette.responses import StreamingResponse
from pdf_utils.config import UPLOAD_DIR
from web_app.core.database import get_file_info
from web_app.services import epub_service
from web_app.ui.components import error_message, toc_display, epub_image_gallery


def setup_routes(app, rt):
    """Register all EPUB processing routes."""

    # ── Metadata ──────────────────────────────────────────────────────────────

    @rt("/epub-metadata/{file_hash}")
    def epub_metadata(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        try:
            meta = epub_service.get_epub_metadata(UPLOAD_DIR / file_info.stored_filename)
        except Exception as e:
            return Div(error_message(f"Error reading metadata: {e}"))

        fields = [
            ("Title",       meta.get("title")),
            ("Author",      meta.get("author")),
            ("Language",    meta.get("language")),
            ("Publisher",   meta.get("publisher")),
            ("Date",        meta.get("date")),
            ("Identifier",  meta.get("identifier")),
            ("Rights",      meta.get("rights")),
            ("Description", meta.get("description")),
        ]
        rows = [
            Tr(Td(label, style="font-weight:600;padding:.3rem .6rem .3rem 0;white-space:nowrap;"),
               Td(value or "—", style="padding:.3rem 0 .3rem .6rem;word-break:break-word;"))
            for label, value in fields if value
        ]

        return Div(
            H3("Book Metadata"),
            Table(Tbody(*rows),
                  style="width:100%;border-collapse:collapse;font-size:.88rem;"),
            cls="result-area",
        )

    # ── TOC ───────────────────────────────────────────────────────────────────

    @rt("/process/epub-toc/{file_hash}", methods=["POST"])
    def process_epub_toc(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        try:
            toc = epub_service.get_epub_toc(UPLOAD_DIR / file_info.stored_filename)
        except Exception as e:
            return Div(error_message(f"Error reading TOC: {e}"))

        if not toc:
            return Div(
                H3("Table of Contents"),
                P("This EPUB has no navigation document.", cls="warning"),
                cls="result-area",
            )
        # Reuse existing toc_display; entry_number acts as the "page" surrogate
        return toc_display(toc)

    # ── Text extraction ───────────────────────────────────────────────────────

    @rt("/epub-text-form/{file_hash}")
    def epub_text_form(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))

        chapter_count = file_info.page_count  # stored as chapter count on upload

        return Div(
            H3("Extract Text"),
            Span(f"{chapter_count} chapters total", cls="pill",
                 style="display:inline-block;margin-bottom:.75rem;"),
            Form(
                Div(
                    Div(Label("Start Chapter"),
                        Input(type="number", name="start_ch",
                              min="1", max=str(chapter_count),
                              value="1", required=True)),
                    Div(Label("End Chapter"),
                        Input(type="number", name="end_ch",
                              min="1", max=str(chapter_count),
                              value=str(chapter_count), required=True)),
                    cls="form-row",
                ),
                Div(
                    Button("Extract Text", type="submit"),
                    Span(Span(cls="spinner"), " Extracting…",
                         id="epub-text-indicator", cls="htmx-indicator"),
                    cls="action-row",
                ),
                hx_post=f"/process/epub-text/{file_hash}",
                hx_target="#operation-result",
                hx_indicator="#epub-text-indicator",
            ),
            cls="result-area",
        )

    @rt("/process/epub-text/{file_hash}", methods=["POST"])
    async def process_epub_text(file_hash: str, start_ch: int, end_ch: int):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))

        chapter_count = file_info.page_count
        if start_ch < 1 or end_ch > chapter_count or start_ch > end_ch:
            return Div(error_message("Invalid chapter range."))

        try:
            import asyncio
            t0 = time.time()
            text = await asyncio.to_thread(
                epub_service.extract_epub_text,
                UPLOAD_DIR / file_info.stored_filename,
                start_ch, end_ch,
            )
            elapsed = time.time() - t0
        except Exception as e:
            return Div(error_message(f"Error extracting text: {e}"))

        base = file_info.stored_filename.rsplit(".", 1)[0]
        md_filename = f"epub_{base}_ch{start_ch}-{end_ch}.md"
        md_path = UPLOAD_DIR / md_filename
        md_path.write_text(text, encoding="utf-8")

        preview_id = f"epub-text-{file_hash}-{start_ch}-{end_ch}"
        return Div(
            H3("Text Extracted"),
            Div(
                Div(P("Characters", cls="metric-label"),
                    P(f"{len(text):,}", cls="metric-value"), cls="metric-box"),
                Div(P("Words", cls="metric-label"),
                    P(f"{len(text.split()):,}", cls="metric-value"), cls="metric-box"),
                Div(P("Chapters", cls="metric-label"),
                    P(str(end_ch - start_ch + 1), cls="metric-value"), cls="metric-box"),
                Div(P("Time", cls="metric-label"),
                    P(f"{elapsed:.1f}s", cls="metric-value"), cls="metric-box"),
                cls="metrics-row", style="margin-bottom:.875rem;",
            ),
            Div(
                A("⬇ Download .md", href=f"/{md_filename}", download=md_filename,
                  cls="button", style="background:var(--green);"),
                Button(
                    "📋 Copy",
                    onclick=(
                        f"const btn=this;"
                        f"fetch('/{md_filename}').then(r=>r.text())"
                        f".then(t=>navigator.clipboard.writeText(t))"
                        f".then(()=>{{"
                        f"btn.textContent='✅ Copied!';btn.style.background='var(--green)';"
                        f"setTimeout(()=>{{btn.textContent='📋 Copy';btn.style.background='';}},2000);}});"
                    ),
                    cls="button",
                ),
                cls="action-row",
            ),
            H4("Preview"),
            Pre(text[:3000] + ("\n…" if len(text) > 3000 else ""),
                id=preview_id, cls="text-preview"),
            cls="result-area",
        )

    # ── Image extraction ──────────────────────────────────────────────────────

    @rt("/epub-images-form/{file_hash}")
    def epub_images_form(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))

        return Div(
            H3("Extract Images"),
            P("Extracts all embedded images from the EPUB package.",
              style="font-size:.88rem;color:var(--text-muted);margin-bottom:.75rem;"),
            Form(
                Div(
                    Button("Extract Images", type="submit"),
                    Span(Span(cls="spinner"), " Extracting…",
                         id="epub-images-indicator", cls="htmx-indicator"),
                    cls="action-row",
                ),
                hx_post=f"/process/epub-images/{file_hash}",
                hx_target="#operation-result",
                hx_indicator="#epub-images-indicator",
            ),
            cls="result-area",
        )

    @rt("/process/epub-images/{file_hash}", methods=["POST"])
    async def process_epub_images(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        try:
            import asyncio
            images_data = await asyncio.to_thread(
                epub_service.extract_epub_images,
                UPLOAD_DIR / file_info.stored_filename,
            )
        except Exception as e:
            return Div(error_message(f"Error extracting images: {e}"))

        return epub_image_gallery(images_data, file_hash)

    @rt("/epub-download-image-zip/{file_hash}")
    async def epub_download_image_zip(file_hash: str):
        """Stream a ZIP of all EPUB images."""
        import zipfile as zf_mod, asyncio
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        try:
            images_data = await asyncio.to_thread(
                epub_service.extract_epub_images,
                UPLOAD_DIR / file_info.stored_filename,
            )
        except Exception as e:
            return Div(error_message(f"Error building ZIP: {e}"))

        if not images_data:
            return Div(error_message("No images found."))

        buf = io.BytesIO()
        with zf_mod.ZipFile(buf, "w", zf_mod.ZIP_DEFLATED) as zf:
            for _group, imgs in images_data.items():
                for img in imgs:
                    zf.writestr(img["filename"], img["raw_data"])
        buf.seek(0)

        stem = Path(file_info.stored_filename).stem
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{stem}_images.zip"'},
        )

    # ── Chapters ZIP ──────────────────────────────────────────────────────────

    @rt("/epub-chapters-form/{file_hash}")
    def epub_chapters_form(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))

        return Div(
            H3("Download All Chapters"),
            P(f"Converts all {file_info.page_count} chapters to Markdown and packages them as a ZIP file.",
              style="font-size:.88rem;color:var(--text-muted);margin-bottom:.75rem;"),
            Form(
                Div(
                    Button("Download Chapters ZIP", type="submit",
                           style="background:var(--orange);"),
                    Span(Span(cls="spinner"), " Converting chapters…",
                         id="epub-chapters-indicator", cls="htmx-indicator"),
                    cls="action-row",
                ),
                hx_post=f"/process/epub-chapters/{file_hash}",
                hx_target="#operation-result",
                hx_indicator="#epub-chapters-indicator",
            ),
            cls="result-area",
        )

    @rt("/process/epub-chapters/{file_hash}", methods=["POST"])
    async def process_epub_chapters(file_hash: str):
        file_info = get_file_info(file_hash)
        if not file_info:
            return Div(error_message("File not found."))
        try:
            import asyncio
            t0 = time.time()
            zip_bytes = await asyncio.to_thread(
                epub_service.extract_epub_chapters_zip,
                UPLOAD_DIR / file_info.stored_filename,
            )
            elapsed = time.time() - t0
        except Exception as e:
            return Div(error_message(f"Error creating chapters ZIP: {e}"))

        stem = Path(file_info.stored_filename).stem
        zip_filename = f"epub_{stem}_chapters.zip"
        zip_path = UPLOAD_DIR / zip_filename
        zip_path.write_bytes(zip_bytes)

        return Div(
            H3("Chapters Ready"),
            Div(
                Div(P("Chapters", cls="metric-label"),
                    P(str(file_info.page_count), cls="metric-value"), cls="metric-box"),
                Div(P("ZIP size", cls="metric-label"),
                    P(f"{len(zip_bytes)/1024:.0f} KB", cls="metric-value"), cls="metric-box"),
                Div(P("Time", cls="metric-label"),
                    P(f"{elapsed:.1f}s", cls="metric-value"), cls="metric-box"),
                cls="metrics-row", style="margin-bottom:.875rem;",
            ),
            Div(
                A("⬇ Download ZIP", href=f"/{zip_filename}", download=zip_filename,
                  cls="button", style="background:var(--orange);"),
                cls="action-row",
            ),
            cls="result-area",
        )
