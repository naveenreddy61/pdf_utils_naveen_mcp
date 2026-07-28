"""Camera-capture handwriting OCR routes.

Holds a paper notebook up to a webcam or tablet camera and transcribes it. The frame is
processed in memory and never written to disk — unlike the upload flow, there is no reason
to keep either the image or the text.
"""

import traceback
from starlette.requests import Request
from fasthtml.common import *
from pdf_utils.config import (
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
    HANDWRITING_OCR_MODEL,
    HANDWRITING_THINKING_LEVEL,
)
from web_app.services.ocr_service import load_prompt, ocr_image_bytes
from web_app.ui.components import capture_page, notebook_ocr_result, error_message

_HANDWRITING_PROMPT_FALLBACK = (
    "Transcribe the handwritten notes in this photograph verbatim. Do not summarise, "
    "rephrase, or correct spelling. The image shows either one page or two facing pages; "
    "if two, transcribe the left page, then a line containing only '--- page break ---', "
    "then the right page. Preserve line breaks and bullets. Mark words you cannot read "
    "confidently with [?] and unreadable passages with [illegible]. Output only the "
    "transcription."
)


def load_handwriting_prompt() -> str:
    """Load the handwriting transcription system instruction."""
    return load_prompt("ocr_prompt_handwriting.txt", _HANDWRITING_PROMPT_FALLBACK)


def setup_routes(app, rt):

    @rt('/capture')
    def capture():
        """Camera capture page for transcribing a held-up notebook."""
        return capture_page()

    @rt('/process/notebook-ocr', methods=['POST'])
    async def process_notebook_ocr(request: Request):
        """OCR a single camera frame. Nothing is persisted."""
        try:
            form = await request.form()
            frame = form.get("frame")

            if frame is None:
                return error_message("No image was received. Capture a frame first.")

            image_bytes = await frame.read()

            if not image_bytes:
                return error_message(
                    "The captured frame was empty. Try again — if the preview is black, "
                    "the camera may still be starting up."
                )

            if len(image_bytes) > MAX_FILE_SIZE_BYTES:
                return error_message(
                    f"Captured frame is larger than {MAX_FILE_SIZE_MB} MB."
                )

            results = await ocr_image_bytes(
                image_bytes,
                mime_type=frame.content_type or "image/jpeg",
                label="notebook capture",
                system_instruction=load_handwriting_prompt(),
                model=HANDWRITING_OCR_MODEL,
                thinking_level=HANDWRITING_THINKING_LEVEL,
                # Camera frames are never byte-identical, so a cache lookup would always
                # miss while still persisting the transcription for the retention window.
                use_cache=False,
                progress_callback=lambda m: print(f"Notebook OCR: {m}", flush=True),
            )

            if results.get("method") == "failed":
                return error_message(
                    f"Transcription failed: {results.get('error', 'unknown error')}"
                )

            if not results["full_text"].strip():
                return error_message(
                    "The model returned no text. Check that the page is in frame, in "
                    "focus, and well lit, then retake."
                )

            return notebook_ocr_result(results)

        except Exception as exc:
            traceback.print_exc()
            return error_message(f"Transcription failed: {exc}")
