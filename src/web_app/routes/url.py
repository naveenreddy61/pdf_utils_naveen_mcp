"""URL-to-Markdown and URL-to-PDF-OCR routes."""

import uuid
from starlette.requests import Request
from fasthtml.common import *
from pdf_utils.config import UPLOAD_DIR
from web_app.services.url_service import extract_url_to_markdown
from web_app.services.url_pdf_service import extract_url_via_pdf_ocr
from web_app.ui.components import error_message, url_result_display, url_pdf_ocr_result_display


def setup_routes(app, rt):

    @rt('/process/url-to-markdown', methods=['POST'])
    async def process_url(request: Request):
        form = await request.form()
        url = (form.get("url") or "").strip()

        if not url:
            return error_message("Please enter a URL.")

        include_links  = form.get("include_links")  != "off"
        include_images = form.get("include_images") == "on"
        include_tables = form.get("include_tables") != "off"

        result = await extract_url_to_markdown(
            url,
            include_links=include_links,
            include_images=include_images,
            include_tables=include_tables,
        )

        if result.error:
            return error_message(result.error)

        # Build file content with source URL header/footer
        source_line = f"Source: {result.url}"
        file_content = f"{source_line}\n\n---\n\n{result.markdown}\n\n---\n\n{source_line}\n"

        md_filename = f"url_{uuid.uuid4().hex[:8]}.md"
        md_path = UPLOAD_DIR / md_filename
        md_path.write_text(file_content, encoding="utf-8")

        return url_result_display(result, md_filename, file_content)

    @rt('/process/url-to-pdf-ocr', methods=['POST'])
    async def process_url_pdf_ocr(request: Request):
        form = await request.form()
        url = (form.get("url") or "").strip()

        if not url:
            return error_message("Please enter a URL.")

        result = await extract_url_via_pdf_ocr(url)

        if result.error:
            return error_message(result.error)

        # Save text result for download
        source_line = f"Source: {result.url}"
        file_content = f"{source_line}\n\n---\n\n{result.text}\n\n---\n\n{source_line}\n"

        txt_filename = f"url_ocr_{uuid.uuid4().hex[:8]}.txt"
        txt_path = UPLOAD_DIR / txt_filename
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(file_content, encoding="utf-8")

        return url_pdf_ocr_result_display(result, txt_filename, file_content)
