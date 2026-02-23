"""Main routes for the web application."""

import asyncio
import uuid
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
    upload_form, file_info_display, operation_buttons,
    error_message, upload_progress_poll, upload_progress_status,
)

# Map MIME types / extensions to internal file_type labels
_CONTENT_TYPE_MAP = {
    "application/pdf": "pdf",
    "image/jpeg":      "image",
    "image/png":       "image",
    "image/webp":      "image",
}
_EXT_MAP = {
    ".pdf":  ("application/pdf", "pdf"),
    ".jpg":  ("image/jpeg",      "image"),
    ".jpeg": ("image/jpeg",      "image"),
    ".png":  ("image/png",       "image"),
    ".webp": ("image/webp",      "image"),
}

# ── In-memory task store (per-process; fine for single-worker deployments) ───
# Structure: { task_id: { "phase": str, "pct": int }
#                      | { "phase": "done",  "result": (FileRecord, bool) }
#                      | { "phase": "error", "error": str } }
_tasks: dict[str, dict] = {}


def _file_type_from_name(filename: str) -> tuple[str, str] | None:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXT_MAP.get(ext)


def _build_file_result_fragment(file_info, is_existing: bool):
    """Return the HTMX fragment shown after a successful upload."""
    return Div(
        file_info_display(file_info, is_existing),
        operation_buttons(file_info.file_hash, file_info.file_type),
    )


async def _register_local_file(content: bytes, original_filename: str, file_type: str):
    """Hash content, dedup against DB, write to disk, return (FileRecord, is_existing)."""
    file_hash = calculate_file_hash(content)
    existing  = get_file_info(file_hash)
    if existing:
        update_last_accessed(file_hash)
        return existing, True

    safe_filename  = sanitize_filename(original_filename)
    stored_filename = f"{file_hash[:8]}_{safe_filename}"
    file_path      = UPLOAD_DIR / stored_filename

    await asyncio.to_thread(file_path.write_bytes, content)

    page_count = (
        await asyncio.to_thread(get_page_count, file_path) if file_type == "pdf" else 1
    )
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


async def _run_upload_task(
    task_id: str,
    content: bytes,
    original_filename: str,
    file_type: str,
) -> None:
    """Background coroutine: process upload and store result in _tasks."""
    try:
        _tasks[task_id] = {"phase": "Hashing file…", "pct": 20}
        await asyncio.sleep(0)  # yield so the polling response goes out first

        file_hash = calculate_file_hash(content)

        _tasks[task_id] = {"phase": "Checking for duplicates…", "pct": 40}
        await asyncio.sleep(0)

        existing = get_file_info(file_hash)
        if existing:
            update_last_accessed(file_hash)
            _tasks[task_id] = {"phase": "done", "pct": 100,
                                "result": (existing, True)}
            return

        _tasks[task_id] = {"phase": "Saving file…", "pct": 60}
        await asyncio.sleep(0)

        safe_filename   = sanitize_filename(original_filename)
        stored_filename = f"{file_hash[:8]}_{safe_filename}"
        file_path       = UPLOAD_DIR / stored_filename
        await asyncio.to_thread(file_path.write_bytes, content)

        _tasks[task_id] = {"phase": "Reading document info…", "pct": 82}
        await asyncio.sleep(0)

        page_count = (
            await asyncio.to_thread(get_page_count, file_path) if file_type == "pdf" else 1
        )
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

        _tasks[task_id] = {"phase": "done", "pct": 100,
                           "result": (file_info, False)}

    except Exception as exc:
        import traceback; traceback.print_exc()
        _tasks[task_id] = {"phase": "error", "pct": 0, "error": str(exc)}


def setup_routes(app, rt):
    """Set up main routes for the application."""

    # ── Index ────────────────────────────────────────────────────────────────

    @rt('/')
    def index():
        return Titled("PDF & Image Utilities",
            Div(
                Div(
                    H1("PDF & Image Utilities", cls="page-title"),
                    P(
                        f"Upload a PDF or image · PDF, JPG, PNG, WEBP · "
                        f"max {MAX_FILE_SIZE_MB} MB · files kept 30 days",
                        cls="page-subtitle",
                    ),
                    cls="page-header",
                ),
                upload_form(),
                cls="app-wrap",
            )
        )

    # ── Upload (HTMX multipart POST) ─────────────────────────────────────────

    @rt('/upload', methods=['POST'])
    async def upload(request: Request):
        """Receive file, validate, spin up background task, return polling UI."""
        try:
            form = await request.form()
            # Support both 'file' (new form) and 'pdf_file' (legacy fallback)
            upload_field = form.get('file') or form.get('pdf_file')

            if not upload_field or not hasattr(upload_field, 'filename'):
                return error_message("No file received – please select a file.")

            filename_lower = upload_field.filename.lower()
            type_info = _file_type_from_name(filename_lower)
            if not type_info:
                return error_message(
                    "Unsupported file type. Allowed: PDF, JPG, JPEG, PNG, WEBP."
                )
            _, file_type = type_info

            content = await upload_field.read()

            if len(content) > MAX_FILE_SIZE_BYTES:
                return error_message(
                    f"File is too large (max {MAX_FILE_SIZE_MB} MB)."
                )
            if len(content) == 0:
                return error_message("File is empty.")

            task_id = uuid.uuid4().hex[:12]
            _tasks[task_id] = {"phase": "Starting…", "pct": 5}

            asyncio.create_task(
                _run_upload_task(task_id, content, upload_field.filename, file_type)
            )
            # Schedule automatic cleanup of abandoned tasks after 5 min
            asyncio.get_event_loop().call_later(
                300, lambda: _tasks.pop(task_id, None)
            )

            return upload_progress_poll(task_id)

        except Exception as exc:
            import traceback; traceback.print_exc()
            return error_message(f"Upload error: {exc}")

    # ── Upload status polling (4 Hz) ─────────────────────────────────────────

    @rt('/upload-status/{task_id}')
    def upload_status(task_id: str):
        """Polled by HTMX every 250 ms.  Returns either:
        - A fresh progress bar (still processing)
        - The file info + operation buttons (done)
        - An error message (failed)
        """
        task = _tasks.get(task_id)

        if task is None:
            return error_message("Upload session expired – please try again.")

        if task["phase"] == "done":
            file_info, is_existing = task["result"]
            _tasks.pop(task_id, None)
            return _build_file_result_fragment(file_info, is_existing)

        if task["phase"] == "error":
            err = task.get("error", "Unknown error")
            _tasks.pop(task_id, None)
            return error_message(f"Upload failed: {err}")

        # Still in progress – return self-refreshing polling div
        return Div(
            upload_progress_status(task["phase"], task["pct"]),
            id="upload-poll",
            hx_get=f"/upload-status/{task_id}",
            hx_trigger="every 250ms",
            hx_target="this",
            hx_swap="outerHTML",
        )

    # ── GCS direct-upload API routes (kept for backward compat) ──────────────

    @rt('/api/request-upload', methods=['POST'])
    async def request_upload(request: Request):
        """Return a signed GCS PUT URL (only when GCS is configured)."""
        if not GCS_BUCKET_NAME:
            return JSONResponse({"error": "GCS not configured."}, status_code=503)

        try:
            body         = await request.json()
            filename     = str(body.get("filename", ""))
            size         = int(body.get("size", 0))
            content_type = str(body.get("content_type", "application/octet-stream"))
        except Exception:
            return JSONResponse({"error": "Invalid request body."}, status_code=400)

        if not filename:
            return JSONResponse({"error": "filename required."}, status_code=400)

        type_info = _file_type_from_name(filename.lower())
        if not type_info:
            return JSONResponse(
                {"error": "Unsupported file type."},
                status_code=400,
            )
        if size > MAX_FILE_SIZE_BYTES:
            return JSONResponse(
                {"error": f"File exceeds {MAX_FILE_SIZE_MB} MB limit."},
                status_code=413,
            )

        expected_content_type, _ = type_info
        try:
            from web_app.services.gcs_service import generate_upload_signed_url
            signed_url, gcs_object_name = await asyncio.to_thread(
                generate_upload_signed_url,
                GCS_BUCKET_NAME, filename, expected_content_type,
                GCS_CREDENTIALS_FILE, GCS_SIGNED_URL_EXPIRY_MINUTES,
            )
        except Exception as exc:
            import traceback; traceback.print_exc()
            return JSONResponse({"error": f"Could not generate URL: {exc}"}, status_code=500)

        return JSONResponse({
            "signed_url": signed_url,
            "gcs_object_name": gcs_object_name,
            "content_type": expected_content_type,
        })

    @rt('/api/confirm-upload', methods=['POST'])
    async def confirm_upload(request: Request):
        """Pull a GCS-uploaded file to local storage and register it."""
        if not GCS_BUCKET_NAME:
            return error_message("GCS not configured.")

        try:
            body             = await request.json()
            gcs_object_name  = str(body.get("gcs_object_name", ""))
            original_filename = str(body.get("original_filename", "unknown"))
        except Exception:
            return error_message("Invalid confirm-upload request.")

        if not gcs_object_name:
            return error_message("gcs_object_name is required.")

        type_info = _file_type_from_name(original_filename.lower())
        if not type_info:
            return error_message("Unsupported file type.")
        _, file_type = type_info

        safe_tmp = sanitize_filename(original_filename)
        tmp_path = UPLOAD_DIR / f"gcs_tmp_{safe_tmp}"

        try:
            from web_app.services.gcs_service import download_from_gcs, delete_from_gcs

            print(f"Pulling {gcs_object_name} from GCS …")
            await download_from_gcs(GCS_BUCKET_NAME, gcs_object_name, tmp_path,
                                    GCS_CREDENTIALS_FILE)

            content   = tmp_path.read_bytes()
            file_info, is_existing = await _register_local_file(
                content, original_filename, file_type
            )

            if GCS_DELETE_AFTER_DOWNLOAD:
                try:
                    await delete_from_gcs(GCS_BUCKET_NAME, gcs_object_name,
                                         GCS_CREDENTIALS_FILE)
                except Exception as del_err:
                    print(f"Warning: could not delete GCS temp: {del_err}")

            return _build_file_result_fragment(file_info, is_existing)

        except Exception as exc:
            import traceback; traceback.print_exc()
            return error_message(f"Error processing file: {exc}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
