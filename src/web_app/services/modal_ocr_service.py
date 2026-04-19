"""OCR service backed by a Modal-hosted GPU endpoint.

Mirrors the public contract of `ocr_service.process_document_async` exactly so
routes can swap between backends by only changing the module reference. See the
plan in /root/.claude/plans/warm-napping-snowglobe.md for design rationale.

Key differences from the Gemini backend:
  - Image-based (not PDF-native): each page is rendered to PNG via PyMuPDF.
  - HTTP transport via httpx to the Modal @fastapi_endpoint.
  - Token counts are always 0 (self-hosted model, no per-token billing).
  - Cache key is model-aware to prevent collisions across backends/models.
  - Page-method label is "llm" (kept for UI compatibility with the shared
    `ocr_result_display` component).
"""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import pymupdf

from pdf_utils.config import (
    OCR_MAX_RETRIES,
    OCR_MODAL_CONCURRENT_REQUESTS,
    OCR_MODAL_DPI,
    OCR_MODAL_ENDPOINT,
    OCR_MODAL_MODEL_ID,
    OCR_MODAL_TIMEOUT,
    OCR_MODAL_TOKEN_ID,
    OCR_MODAL_TOKEN_SECRET,
    OCR_RETRY_DELAY_BASE,
)

from .ocr_cache import (
    clean_old_cache_entries,
    compute_content_hash,
    get_cached_ocr,
    init_cache_database,
    save_ocr_to_cache,
)
from .ocr_service import extract_with_pymupdf_fallback


# ---------------------------------------------------------------------------
# Cache key — model-aware so Gemini and Modal entries cannot collide.
# ---------------------------------------------------------------------------

def _modal_cache_key(pdf_path: Path, page_num: int, model_id: str) -> str:
    stats = pdf_path.stat()
    raw = f"modal:{model_id}:{pdf_path.name}:{stats.st_size}:{stats.st_mtime}:{page_num}"
    return compute_content_hash(raw.encode("utf-8"))


# ---------------------------------------------------------------------------
# Page rendering — PyMuPDF in a thread to avoid blocking the event loop.
# ---------------------------------------------------------------------------

async def _render_page_to_png(pdf_path: Path, page_num: int, dpi: int) -> bytes:
    def _sync() -> bytes:
        doc = pymupdf.open(pdf_path)
        try:
            page = doc[page_num - 1]
            matrix = pymupdf.Matrix(dpi / 72, dpi / 72)
            pixmap = page.get_pixmap(matrix=matrix)
            return pixmap.tobytes("png")
        finally:
            doc.close()

    return await asyncio.to_thread(_sync)


# ---------------------------------------------------------------------------
# Modal endpoint call.
# ---------------------------------------------------------------------------

async def _post_to_modal(client: httpx.AsyncClient, image_bytes: bytes) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if OCR_MODAL_TOKEN_ID and OCR_MODAL_TOKEN_SECRET:
        headers = {
            "Modal-Key": OCR_MODAL_TOKEN_ID,
            "Modal-Secret": OCR_MODAL_TOKEN_SECRET,
        }

    response = await client.post(
        OCR_MODAL_ENDPOINT,
        json={"image_base64": base64.b64encode(image_bytes).decode()},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Single-page OCR (render → cache → call → cache save).
# ---------------------------------------------------------------------------

async def _ocr_page(
    pdf_path: Path,
    page_num: int,
    pdf_filename: str,
    client: httpx.AsyncClient,
) -> Tuple[str, str]:
    """Returns (text, method) where method is "cached" or "llm"."""
    cache_key = _modal_cache_key(pdf_path, page_num, OCR_MODAL_MODEL_ID)

    cached = await get_cached_ocr(cache_key)
    if cached:
        text, _, _ = cached
        return text, "cached"

    image_bytes = await _render_page_to_png(pdf_path, page_num, OCR_MODAL_DPI)
    data = await _post_to_modal(client, image_bytes)

    if not data.get("success", False):
        raise RuntimeError(data.get("error") or "Modal OCR returned success=False")

    text = data.get("text", "")
    await save_ocr_to_cache(cache_key, text, 0, 0, pdf_filename, page_num)
    return text, "llm"


# ---------------------------------------------------------------------------
# Per-page task (semaphore-guarded).
# ---------------------------------------------------------------------------

async def _process_page(
    pdf_path: Path,
    page_num: int,
    semaphore: asyncio.Semaphore,
    pdf_filename: str,
    client: httpx.AsyncClient,
) -> Dict[str, Any]:
    async with semaphore:
        try:
            text, method = await _ocr_page(pdf_path, page_num, pdf_filename, client)
            return {
                "page": page_num,
                "text": text.strip(),
                "input_tokens": 0,
                "output_tokens": 0,
                "method": method,
                "success": True,
                "error": None,
                "retry_count": 0,
            }
        except Exception as exc:
            return {
                "page": page_num,
                "text": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "method": "failed",
                "success": False,
                "error": str(exc),
                "retry_count": 0,
            }


async def _retry_failed_pages(
    failed: List[Dict[str, Any]],
    attempt: int,
    pdf_path: Path,
    semaphore: asyncio.Semaphore,
    pdf_filename: str,
    client: httpx.AsyncClient,
) -> List[Dict[str, Any]]:
    delay = OCR_RETRY_DELAY_BASE * (2 ** (attempt - 1))
    await asyncio.sleep(delay)

    print(f"[modal_ocr] Retrying {len(failed)} failed pages (attempt {attempt})")

    tasks = [
        _process_page(pdf_path, r["page"], semaphore, pdf_filename, client)
        for r in failed
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: List[Dict[str, Any]] = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            out.append({
                "page": failed[i]["page"],
                "text": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "method": "failed",
                "success": False,
                "error": str(res),
                "retry_count": attempt,
            })
        else:
            res["retry_count"] = attempt
            out.append(res)
    return out


# ---------------------------------------------------------------------------
# Public API — matches ocr_service.process_document_async.
# ---------------------------------------------------------------------------

async def process_document_async(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    if not OCR_MODAL_ENDPOINT:
        raise EnvironmentError(
            "Modal OCR requires OCR_MODAL_ENDPOINT.\n"
            "Deploy first:  uv run modal deploy modal_app/ocr_app.py\n"
            "Then set OCR_MODAL_ENDPOINT in .env to the URL Modal printed."
        )

    await init_cache_database()

    start_time = time.time()
    pdf_filename = pdf_path.name
    page_list = list(range(start_page, end_page + 1))
    total_pages = len(page_list)

    if progress_callback:
        progress_callback(
            f"Processing {total_pages} pages via Modal ({OCR_MODAL_MODEL_ID})"
        )

    semaphore = asyncio.Semaphore(OCR_MODAL_CONCURRENT_REQUESTS)

    async with httpx.AsyncClient(timeout=OCR_MODAL_TIMEOUT) as client:
        initial_tasks = [
            _process_page(pdf_path, p, semaphore, pdf_filename, client)
            for p in page_list
        ]
        initial = await asyncio.gather(*initial_tasks, return_exceptions=True)

        all_results: List[Dict[str, Any]] = []
        for i, res in enumerate(initial):
            if isinstance(res, Exception):
                all_results.append({
                    "page": page_list[i],
                    "text": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "method": "failed",
                    "success": False,
                    "error": str(res),
                    "retry_count": 0,
                })
            else:
                all_results.append(res)

        failed = [r for r in all_results if not r["success"]]
        for attempt in range(1, OCR_MAX_RETRIES + 1):
            if not failed:
                break
            retry_out = await _retry_failed_pages(
                failed, attempt, pdf_path, semaphore, pdf_filename, client
            )
            recovered = []
            still_failed = []
            for rr in retry_out:
                if rr["success"]:
                    recovered.append(rr)
                    for j, orig in enumerate(all_results):
                        if orig["page"] == rr["page"]:
                            all_results[j] = rr
                            break
                else:
                    still_failed.append(rr)
            failed = still_failed
            if progress_callback and recovered:
                progress_callback(
                    f"Recovered {len(recovered)} pages on retry {attempt}"
                )

    # PyMuPDF fallback for anything still failing after retries.
    final_failed = [r for r in all_results if not r["success"]]
    if final_failed:
        if progress_callback:
            progress_callback(
                f"Applying offline extraction to {len(final_failed)} pages"
            )
        for fr in final_failed:
            try:
                fr.update({
                    "text": extract_with_pymupdf_fallback(pdf_path, fr["page"]),
                    "method": "pymupdf_fallback",
                    "success": True,
                    "error": None,
                })
            except Exception as exc:
                fr["error"] = f"Fallback failed: {exc}"

    all_results.sort(key=lambda r: r["page"])

    text_parts: List[str] = []
    cached_pages: List[int] = []
    llm_pages: List[int] = []
    fallback_pages: List[int] = []

    for r in all_results:
        if r["text"]:
            text_parts.append(f"--- Page {r['page']} ---\n{r['text']}")
        if r["method"] == "cached":
            cached_pages.append(r["page"])
        elif r["method"] == "llm":
            llm_pages.append(r["page"])
        elif r["method"] == "pymupdf_fallback":
            fallback_pages.append(r["page"])

    processing_time = time.time() - start_time
    asyncio.create_task(clean_old_cache_entries())

    cached_count = len(cached_pages)
    cache_note = f" ({cached_count} from cache)" if cached_count else ""
    summary = (
        f"Modal OCR ({OCR_MODAL_MODEL_ID}): "
        f"{len(llm_pages)} pages via GPU{cache_note}, "
        f"{len(fallback_pages)} via PyMuPDF fallback"
    )
    if progress_callback:
        progress_callback(f"✅ Complete: {summary}")

    return {
        "full_text": "\n\n".join(text_parts),
        "text_parts": text_parts,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "successful_pages": [r["page"] for r in all_results if r["success"]],
        "failed_pages": [
            {"page": r["page"], "error": r["error"]}
            for r in all_results if not r["success"]
        ],
        "cached_pages": cached_pages,
        "llm_pages": llm_pages,
        "fallback_pages": fallback_pages,
        "processing_time": processing_time,
        "pages_processed": len(all_results),
        "retry_count": sum(r["retry_count"] for r in all_results),
        "tokens_saved": 0,
        "summary": summary,
    }


process_pages_async_batch = process_document_async
