"""URL-to-Markdown route."""

import uuid
from starlette.requests import Request
from starlette.responses import Response
from fasthtml.common import *
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

        # Build file content with source URL header/footer
        source_line = f"Source: {result.url}"
        file_content = f"{source_line}\n\n---\n\n{result.markdown}\n\n---\n\n{source_line}\n"

        md_filename = f"url_{uuid.uuid4().hex[:8]}.md"
        md_path = UPLOAD_DIR / md_filename
        md_path.write_text(file_content, encoding="utf-8")

        return url_result_display(result, md_filename, file_content)

    @rt('/download/url-md/{filename}')
    def download_url_md(filename: str):
        if not filename.startswith('url_') or not filename.endswith('.md'):
            return Response("Not found", status_code=404)
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            return Response("File not found", status_code=404)
        content = file_path.read_text(encoding="utf-8")
        return Response(
            content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
