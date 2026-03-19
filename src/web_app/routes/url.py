"""URL-to-Markdown route."""

import uuid
from pathlib import Path
from fasthtml.common import *
from starlette.requests import Request
from pdf_utils.config import UPLOAD_DIR
from web_app.services.url_service import extract_url_to_markdown
from web_app.ui.components import error_message, url_result_display


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

        # Save markdown file for download
        md_filename = f"url_{uuid.uuid4().hex[:8]}.md"
        md_path = UPLOAD_DIR / md_filename
        md_path.write_text(result.markdown, encoding="utf-8")

        return url_result_display(result, md_filename)
