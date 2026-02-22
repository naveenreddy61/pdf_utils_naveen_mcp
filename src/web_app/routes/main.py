"""Main routes for the web application."""

import asyncio
from datetime import datetime
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import JSONResponse
from pdf_utils.config import (
    UPLOAD_DIR, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS,
    GCS_BUCKET_NAME, GCS_CREDENTIALS_FILE, GCS_SIGNED_URL_EXPIRY_MINUTES,
    GCS_DELETE_AFTER_DOWNLOAD,
)
from web_app.core.database import (
    FileRecord, get_file_info, update_last_accessed, insert_file_record
)
from web_app.core.utils import calculate_file_hash, sanitize_filename
from web_app.services.pdf_service import get_page_count
from web_app.ui.components import (
    upload_form, page_with_result, file_info_display,
    operation_buttons, error_message
)

# Map MIME types / extensions to internal file_type labels
_CONTENT_TYPE_MAP = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
}
_EXT_MAP = {
    ".pdf": ("application/pdf", "pdf"),
    ".jpg": ("image/jpeg", "image"),
    ".jpeg": ("image/jpeg", "image"),
    ".png": ("image/png", "image"),
    ".webp": ("image/webp", "image"),
}


def _file_type_from_name(filename: str) -> tuple[str, str] | None:
    """Return (content_type, file_type) for a filename, or None if unsupported."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXT_MAP.get(ext)


def _build_file_result(file_info, is_existing: bool):
    """Return the HTMX fragment shown after a successful upload."""
    return page_with_result(
        Div(
            file_info_display(file_info, is_existing),
            operation_buttons(file_info.file_hash, file_info.file_type),
            Div(id="operation-result"),
        )
    )


async def _register_local_file(content: bytes, original_filename: str, file_type: str):
    """Hash content, dedup against DB, write to disk, return (FileRecord, is_existing)."""
    file_hash = calculate_file_hash(content)
    existing = get_file_info(file_hash)
    if existing:
        update_last_accessed(file_hash)
        return existing, True

    safe_filename = sanitize_filename(original_filename)
    stored_filename = f"{file_hash[:8]}_{safe_filename}"
    file_path = UPLOAD_DIR / stored_filename
    file_path.write_bytes(content)

    page_count = get_page_count(file_path) if file_type == "pdf" else 1
    file_info = FileRecord(
        file_hash=file_hash,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_size=len(content),
        page_count=page_count,
        file_type=file_type,
        upload_date=datetime.now().isoformat(),
        last_accessed=datetime.now().isoformat(),
    )
    insert_file_record(file_info)
    return file_info, False


def setup_routes(app, rt):
    """Set up main routes for the application."""

    @rt('/')
    def index():
        """Main page with file upload form."""
        return Titled("PDF & Image Utilities",
            Div(
                H2("PDF & Image Processing Tools"),
                P("Upload a PDF or image file to use various processing tools. Files are kept for 30 days."),
                P(f"Maximum file size: {MAX_FILE_SIZE_MB} MB"),
                P("Supported formats: PDF, JPG, JPEG, PNG, WEBP", style="color: #666; font-style: italic;"),
                upload_form(),
                Div(id="upload-result"),
                cls="container",
            )
        )

    # ── Legacy multipart upload (used when GCS is not configured) ────────────

    @rt('/upload', methods=['POST'])
    async def upload(request: Request):
        """Handle multipart file upload with deduplication (fallback path)."""
        try:
            form = await request.form()
            pdf_file = form.get('pdf_file')

            if not pdf_file or not hasattr(pdf_file, 'filename'):
                return page_with_result(error_message("Error: No file was uploaded."))

            filename_lower = pdf_file.filename.lower()
            type_info = _file_type_from_name(filename_lower)
            if not type_info:
                return page_with_result(
                    error_message("Error: Only PDF and image files (JPG, JPEG, PNG, WEBP) are allowed.")
                )
            _, file_type = type_info

            content = await pdf_file.read()

            if len(content) > MAX_FILE_SIZE_BYTES:
                return page_with_result(
                    error_message(f"Error: File size exceeds {MAX_FILE_SIZE_MB} MB limit.")
                )

            file_info, is_existing = await _register_local_file(content, pdf_file.filename, file_type)
            return _build_file_result(file_info, is_existing)

        except Exception as e:
            import traceback; traceback.print_exc()
            return page_with_result(error_message(f"Error uploading file: {e}"))

    # ── GCS direct-upload routes ─────────────────────────────────────────────

    @rt('/api/request-upload', methods=['POST'])
    async def request_upload(request: Request):
        """Return a signed GCS PUT URL so the browser can upload directly.

        Expects JSON body: {filename, size, content_type}
        Returns JSON: {signed_url, gcs_object_name}  or  {error}
        """
        if not GCS_BUCKET_NAME:
            return JSONResponse({"error": "GCS not configured on this server."}, status_code=503)

        try:
            body = await request.json()
            filename: str = body.get("filename", "")
            size: int = int(body.get("size", 0))
            content_type: str = body.get("content_type", "application/octet-stream")
        except Exception:
            return JSONResponse({"error": "Invalid request body."}, status_code=400)

        if not filename:
            return JSONResponse({"error": "filename is required."}, status_code=400)

        type_info = _file_type_from_name(filename.lower())
        if not type_info:
            return JSONResponse(
                {"error": "Unsupported file type. Allowed: PDF, JPG, JPEG, PNG, WEBP."},
                status_code=400,
            )

        if size > MAX_FILE_SIZE_BYTES:
            return JSONResponse(
                {"error": f"File exceeds {MAX_FILE_SIZE_MB} MB limit."},
                status_code=413,
            )

        # Use the correct MIME type regardless of what the browser reports
        expected_content_type, _ = type_info

        try:
            from web_app.services.gcs_service import generate_upload_signed_url
            signed_url, gcs_object_name = await asyncio.to_thread(
                generate_upload_signed_url,
                GCS_BUCKET_NAME,
                filename,
                expected_content_type,
                GCS_CREDENTIALS_FILE,
                GCS_SIGNED_URL_EXPIRY_MINUTES,
            )
        except Exception as e:
            import traceback; traceback.print_exc()
            return JSONResponse({"error": f"Could not generate upload URL: {e}"}, status_code=500)

        return JSONResponse({
            "signed_url": signed_url,
            "gcs_object_name": gcs_object_name,
            "content_type": expected_content_type,
        })

    @rt('/api/confirm-upload', methods=['POST'])
    async def confirm_upload(request: Request):
        """Pull a previously GCS-uploaded file to local storage and register it.

        Expects JSON body: {gcs_object_name, original_filename}
        Returns: HTMX HTML fragment (same as the old /upload response)
        """
        if not GCS_BUCKET_NAME:
            return page_with_result(error_message("GCS not configured on this server."))

        try:
            body = await request.json()
            gcs_object_name: str = body.get("gcs_object_name", "")
            original_filename: str = body.get("original_filename", "unknown")
        except Exception:
            return page_with_result(error_message("Invalid confirm-upload request."))

        if not gcs_object_name:
            return page_with_result(error_message("gcs_object_name is required."))

        type_info = _file_type_from_name(original_filename.lower())
        if not type_info:
            return page_with_result(error_message("Unsupported file type."))
        _, file_type = type_info

        # Download from GCS to a temporary local path, then register
        safe_tmp = sanitize_filename(original_filename)
        tmp_path = UPLOAD_DIR / f"gcs_tmp_{safe_tmp}"

        try:
            from web_app.services.gcs_service import download_from_gcs, delete_from_gcs

            print(f"Pulling {gcs_object_name} from GCS …")
            await download_from_gcs(GCS_BUCKET_NAME, gcs_object_name, tmp_path, GCS_CREDENTIALS_FILE)

            content = tmp_path.read_bytes()
            file_info, is_existing = await _register_local_file(content, original_filename, file_type)

            if GCS_DELETE_AFTER_DOWNLOAD:
                try:
                    await delete_from_gcs(GCS_BUCKET_NAME, gcs_object_name, GCS_CREDENTIALS_FILE)
                    print(f"Deleted temp GCS object {gcs_object_name}")
                except Exception as del_err:
                    print(f"Warning: could not delete GCS temp object: {del_err}")

            return _build_file_result(file_info, is_existing)

        except Exception as e:
            import traceback; traceback.print_exc()
            return page_with_result(error_message(f"Error processing uploaded file: {e}"))
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
