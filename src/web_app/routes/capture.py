"""Camera-capture handwriting OCR routes.

Holds a paper notebook up to a webcam or tablet camera and transcribes it. The
frame is processed in memory and never written to disk — unlike the upload flow,
there is no reason to keep either the image or the text.

A session is one or more accepted frames. Each accepted frame starts a background
OCR task immediately (Next page / Done); the browser only waits after Done for
whichever tasks are still running.
"""

import re
import traceback
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse
from fasthtml.common import *
from pdf_utils.config import (
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    HANDWRITING_OCR_MODEL,
    HANDWRITING_THINKING_LEVEL,
    NOTEBOOK_SESSION_MAX_PAGES,
)
from web_app.core import tasks
from web_app.services.ocr_service import load_prompt, ocr_image_bytes
from web_app.ui.components import capture_page, notebook_session_result

_HANDWRITING_PROMPT_FALLBACK = (
    "Transcribe the handwritten notes in this photograph verbatim. Do not summarise, "
    "rephrase, or correct spelling. The image shows either one page or two facing pages; "
    "if two, transcribe the left page, then a line containing only '--- page break ---', "
    "then the right page. Preserve line breaks and bullets. Mark words you cannot read "
    "confidently with [?] and unreadable ones [illegible]. Output only the "
    "transcription."
)

# tasks.new_task issues 12 hex chars. Reject anything else so a crafted query
# string cannot walk the in-memory store.
_TASK_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def load_handwriting_prompt() -> str:
    """Load the handwriting transcription system instruction."""
    return load_prompt("ocr_prompt_handwriting.txt", _HANDWRITING_PROMPT_FALLBACK)


def parse_task_ids(raw: str) -> list[str]:
    """Split a comma-separated id list, dropping blanks and rejecting junk."""
    ids = []
    for part in (raw or "").split(","):
        tid = part.strip()
        if not tid:
            continue
        if not _TASK_ID_RE.match(tid):
            continue
        ids.append(tid)
    return ids[:NOTEBOOK_SESSION_MAX_PAGES]


def collect_notebook_pages(task_ids: list[str]) -> dict:
    """Summarise a capture session from in-memory OCR tasks.

    Does not pop tasks — the browser may poll again, or add another page and
    re-fetch the same ids.

    status is "pending" until every id is terminal (done, error, or missing).
    """
    pages: list[dict] = []
    pending = 0
    for i, tid in enumerate(task_ids, start=1):
        task = tasks.get_task(tid)
        if task is None:
            pages.append({
                "n": i,
                "ok": False,
                "error": "This page expired. Recapture it.",
                "full_text": "",
                "processing_time": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            })
            continue
        if task["phase"] == "error":
            pages.append({
                "n": i,
                "ok": False,
                "error": task.get("error") or "Transcription failed.",
                "full_text": "",
                "processing_time": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            })
            continue
        if task["phase"] != "done":
            pending += 1
            pages.append({"n": i, "ok": None})
            continue
        result = task["result"] or {}
        pages.append({
            "n": i,
            "ok": True,
            "error": "",
            "full_text": result.get("full_text") or "",
            "processing_time": result.get("processing_time") or 0,
            "total_input_tokens": result.get("total_input_tokens") or 0,
            "total_output_tokens": result.get("total_output_tokens") or 0,
        })
    total = len(task_ids)
    done = total - pending
    if pending:
        return {"status": "pending", "done": done, "total": total}
    return {"status": "done", "done": done, "total": total, "pages": pages}


async def _read_frame(request: Request) -> tuple[Optional[bytes], str, Optional[str]]:
    """Return (bytes, mime_type, error). On error, bytes is None."""
    form = await request.form()
    frame = form.get("frame")
    if frame is None:
        return None, "", "No image was received. Capture a frame first."
    image_bytes = await frame.read()
    if not image_bytes:
        return None, "", (
            "The captured frame was empty. Try again — if the preview is black, "
            "the camera may still be starting up."
        )
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        return None, "", f"Captured frame is larger than {MAX_FILE_SIZE_MB} MB."
    mime = getattr(frame, "content_type", None) or "image/jpeg"
    return image_bytes, mime, None


def setup_routes(app, rt):

    @rt('/capture')
    def capture():
        """Camera capture page for transcribing a held-up notebook."""
        return capture_page()

    @rt('/process/notebook-page', methods=['POST'])
    async def process_notebook_page(request: Request):
        """Accept one frame and start its OCR in the background.

        Returns JSON {ok, task_id} so the browser can keep capturing while this
        page transcribes. Nothing is persisted.
        """
        try:
            image_bytes, mime, error = await _read_frame(request)
            if error:
                return JSONResponse({"ok": False, "error": error}, status_code=400)

            prompt = load_handwriting_prompt()

            async def work(task_id: str):
                results = await ocr_image_bytes(
                    image_bytes,
                    mime_type=mime,
                    label="notebook capture",
                    system_instruction=prompt,
                    model=HANDWRITING_OCR_MODEL,
                    thinking_level=HANDWRITING_THINKING_LEVEL,
                    # Camera frames are never byte-identical, so a cache lookup
                    # would always miss while still persisting the transcription
                    # for the retention window.
                    use_cache=False,
                    progress_callback=lambda m: print(f"Notebook OCR: {m}", flush=True),
                )
                if results.get("method") == "failed":
                    raise RuntimeError(results.get("error") or "unknown error")
                if not (results.get("full_text") or "").strip():
                    raise RuntimeError(
                        "The model returned no text. Check that the page is in "
                        "frame, in focus, and well lit, then recapture it."
                    )
                return results

            task_id = tasks.start_task(work, phase="Transcribing…", pct=10)
            return JSONResponse({"ok": True, "task_id": task_id})
        except Exception as exc:
            traceback.print_exc()
            return JSONResponse(
                {"ok": False, "error": f"Transcription failed: {exc}"},
                status_code=500,
            )

    @rt('/notebook-page-status/{task_id}')
    def notebook_page_status(task_id: str):
        """JSON status of one accepted page, for the filmstrip chips."""
        if not _TASK_ID_RE.match(task_id):
            return JSONResponse({"status": "expired"})
        task = tasks.get_task(task_id)
        if task is None:
            return JSONResponse({"status": "expired"})
        if task["phase"] == "done":
            return JSONResponse({"status": "done"})
        if task["phase"] == "error":
            return JSONResponse({
                "status": "error",
                "error": task.get("error") or "Transcription failed.",
            })
        return JSONResponse({"status": "pending"})

    @rt('/notebook-session-status')
    def notebook_session_status(request: Request):
        """JSON summary of every accepted page. Polled after Done."""
        ids = parse_task_ids(request.query_params.get("ids", ""))
        if not ids:
            return JSONResponse({"error": "No pages."}, status_code=400)
        return JSONResponse(collect_notebook_pages(ids))

    @rt('/notebook-session-result')
    def notebook_session_result_route(request: Request):
        """HTML result panel once every page is terminal."""
        ids = parse_task_ids(request.query_params.get("ids", ""))
        if not ids:
            return P("No pages to show.", cls="error")
        summary = collect_notebook_pages(ids)
        if summary["status"] != "done":
            return P(
                f"Still transcribing {summary['done']} of {summary['total']} pages…",
                cls="error",
            )
        return notebook_session_result(summary["pages"])
