"""
OCR service using DeepSeek OCR 2 via a Modal serverless GPU endpoint.

This module mirrors the public interface of ocr_service.py so that routes can
swap between backends with a single variable:

    service = deepseek_ocr_service if backend == "deepseek_modal" else ocr_service
    results = await service.process_document_async(pdf_path, start, end, cb)

Key differences from the Gemini backend:
  - Each PDF page is rendered to a PNG image (DeepSeek takes images, not PDF bytes).
  - The Modal HTTP endpoint is called via httpx instead of the Google GenAI SDK.
  - Token counts are not tracked (self-hosted model, no per-token billing).
  - Concurrency is capped lower (MODAL_OCR_CONCURRENT_REQUESTS=5) to control GPU cost.
  - The method label in results is "deepseek" instead of "llm".
"""

import asyncio
import base64
import io
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import httpx
import pymupdf
import pymupdf4llm

from pdf_utils.config import (
    MODAL_OCR_ENDPOINT,
    MODAL_TOKEN_ID,
    MODAL_TOKEN_SECRET,
    MODAL_OCR_DPI,
    MODAL_OCR_TIMEOUT,
    MODAL_OCR_CONCURRENT_REQUESTS,
    OCR_MAX_RETRIES,
    OCR_RETRY_DELAY_BASE,
)
from .ocr_cache import (
    clean_old_cache_entries,
    get_cached_ocr,
    init_cache_database,
    save_ocr_to_cache,
)
from .ocr_service import create_cache_key, extract_with_pymupdf_fallback


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

async def _render_page_to_png(pdf_path: Path, page_num: int, dpi: int) -> bytes:
    """Render a single PDF page to PNG bytes (runs in a thread to avoid blocking)."""
    def _sync_render() -> bytes:
        doc = pymupdf.open(pdf_path)
        page = doc[page_num - 1]  # 0-based index
        matrix = pymupdf.Matrix(dpi / 72, dpi / 72)
        pixmap = page.get_pixmap(matrix=matrix)
        png_bytes = pixmap.tobytes("png")
        doc.close()
        return png_bytes

    return await asyncio.to_thread(_sync_render)


# ---------------------------------------------------------------------------
# Modal endpoint call
# ---------------------------------------------------------------------------

async def _call_modal_endpoint(image_bytes: bytes) -> dict:
    """POST a base64-encoded page image to the Modal DeepSeek OCR endpoint."""
    image_b64 = base64.b64encode(image_bytes).decode()

    headers: Dict[str, str] = {}
    if MODAL_TOKEN_ID and MODAL_TOKEN_SECRET:
        headers = {
            "Modal-Key": MODAL_TOKEN_ID,
            "Modal-Secret": MODAL_TOKEN_SECRET,
        }

    async with httpx.AsyncClient(timeout=MODAL_OCR_TIMEOUT) as client:
        response = await client.post(
            MODAL_OCR_ENDPOINT,
            json={"image_base64": image_b64},
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Single-page OCR (with cache)
# ---------------------------------------------------------------------------

async def _ocr_page(
    pdf_path: Path,
    page_num: int,
    pdf_filename: str,
) -> Tuple[str, int, int, str]:
    """
    OCR a single PDF page via DeepSeek OCR 2 on Modal, with cache.

    Returns:
        (text, input_tokens, output_tokens, method)
        method is "cached" or "deepseek"
    """
    cache_key = create_cache_key(pdf_path, [page_num])

    cached = await get_cached_ocr(cache_key)
    if cached:
        text, in_tok, out_tok = cached
        return text, in_tok, out_tok, "cached"

    # Render page → PNG
    image_bytes = await _render_page_to_png(pdf_path, page_num, MODAL_OCR_DPI)

    # Call Modal
    data = await _call_modal_endpoint(image_bytes)

    if not data.get("success", False):
        raise RuntimeError(data.get("error", "DeepSeek OCR endpoint returned failure"))

    text = data.get("text", "")

    # Cache result (token counts are 0 — self-hosted model, no per-token billing)
    await save_ocr_to_cache(cache_key, text, 0, 0, pdf_filename, page_num)

    return text, 0, 0, "deepseek"


# ---------------------------------------------------------------------------
# Per-page task (semaphore-guarded)
# ---------------------------------------------------------------------------

async def _process_page(
    pdf_path: Path,
    page_num: int,
    semaphore: asyncio.Semaphore,
    pdf_filename: str,
) -> Dict:
    """Process one page under the semaphore; return a per-page result dict."""
    async with semaphore:
        try:
            text, in_tok, out_tok, method = await _ocr_page(
                pdf_path, page_num, pdf_filename
            )
            return {
                "page": page_num,
                "text": text.strip(),
                "input_tokens": in_tok,
                "output_tokens": out_tok,
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


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _retry_failed_pages(
    failed_results: List[Dict],
    attempt: int,
    pdf_path: Path,
    semaphore: asyncio.Semaphore,
    pdf_filename: str,
) -> List[Dict]:
    """Retry failed pages with exponential back-off."""
    delay = OCR_RETRY_DELAY_BASE * (2 ** (attempt - 1))
    await asyncio.sleep(delay)

    print(f"[DeepSeek OCR] Retrying {len(failed_results)} failed pages (attempt {attempt})")

    tasks = [
        _process_page(pdf_path, r["page"], semaphore, pdf_filename)
        for r in failed_results
    ]
    retry_results = await asyncio.gather(*tasks, return_exceptions=True)

    out = []
    for i, res in enumerate(retry_results):
        if isinstance(res, Exception):
            original = failed_results[i]
            out.append({
                "page": original["page"],
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
# Public API — mirrors ocr_service.process_document_async exactly
# ---------------------------------------------------------------------------

async def process_document_async(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict:
    """
    Process a PDF with DeepSeek OCR 2 via Modal.

    Signature and return dict are identical to ocr_service.process_document_async
    so routes need no structural changes — just swap the service module.
    """
    if not MODAL_OCR_ENDPOINT:
        raise EnvironmentError(
            "DeepSeek OCR requires MODAL_OCR_ENDPOINT environment variable.\n"
            "Deploy the Modal app: modal deploy modal_app/deepseek_ocr.py\n"
            "Then set: export MODAL_OCR_ENDPOINT='https://...modal.run'"
        )

    await init_cache_database()

    start_time = time.time()
    pdf_filename = pdf_path.name
    total_pages = end_page - start_page + 1
    page_list = list(range(start_page, end_page + 1))

    if progress_callback:
        progress_callback(
            f"Processing {total_pages} pages via DeepSeek OCR 2 on Modal GPU"
        )

    semaphore = asyncio.Semaphore(MODAL_OCR_CONCURRENT_REQUESTS)

    # Initial pass
    tasks = [
        _process_page(pdf_path, page_num, semaphore, pdf_filename)
        for page_num in page_list
    ]
    initial_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: List[Dict] = []
    for i, res in enumerate(initial_results):
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

    # Retry loop
    failed = [r for r in all_results if not r["success"]]
    for attempt in range(1, OCR_MAX_RETRIES + 1):
        if not failed:
            break

        retry_results = await _retry_failed_pages(
            failed, attempt, pdf_path, semaphore, pdf_filename
        )

        recovered, still_failed = [], []
        for rr in retry_results:
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

    # PyMuPDF fallback for any still-failed pages
    final_failed = [r for r in all_results if not r["success"]]
    if final_failed:
        if progress_callback:
            progress_callback(
                f"Applying offline extraction to {len(final_failed)} pages"
            )
        for fr in final_failed:
            try:
                fallback_text = extract_with_pymupdf_fallback(pdf_path, fr["page"])
                fr.update({"text": fallback_text, "method": "pymupdf_fallback",
                            "success": True, "error": None})
            except Exception as exc:
                fr["error"] = f"Fallback failed: {exc}"

    all_results.sort(key=lambda r: r["page"])

    # Aggregate
    text_parts: List[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    cached_pages: List[int] = []
    deepseek_pages: List[int] = []
    fallback_pages: List[int] = []
    tokens_saved = 0

    for r in all_results:
        if r["text"]:
            text_parts.append(f"--- Page {r['page']} ---\n{r['text']}")
        total_input_tokens += r["input_tokens"]
        total_output_tokens += r["output_tokens"]
        if r["method"] == "cached":
            cached_pages.append(r["page"])
            tokens_saved += r["input_tokens"] + r["output_tokens"]
        elif r["method"] == "deepseek":
            deepseek_pages.append(r["page"])
        elif r["method"] == "pymupdf_fallback":
            fallback_pages.append(r["page"])

    processing_time = time.time() - start_time

    asyncio.create_task(clean_old_cache_entries())

    cached_count = len(cached_pages)
    cache_pct = f" ({cached_count} from cache)" if cached_count else ""
    summary = (
        f"DeepSeek OCR: processed {len(deepseek_pages)} pages via GPU"
        f"{cache_pct}, {len(fallback_pages)} via PyMuPDF fallback"
    )
    if progress_callback:
        progress_callback(f"✅ Complete: {summary}")

    return {
        "full_text": "\n\n".join(text_parts),
        "text_parts": text_parts,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "successful_pages": [r["page"] for r in all_results if r["success"]],
        "failed_pages": [
            {"page": r["page"], "error": r["error"]}
            for r in all_results if not r["success"]
        ],
        "cached_pages": cached_pages,
        "llm_pages": deepseek_pages,   # called "llm_pages" for UI compatibility
        "fallback_pages": fallback_pages,
        "processing_time": processing_time,
        "pages_processed": len(all_results),
        "retry_count": sum(r["retry_count"] for r in all_results),
        "tokens_saved": tokens_saved,
        "summary": summary,
    }


# Alias to match ocr_service's exported name used by existing route code
process_pages_async_batch = process_document_async
