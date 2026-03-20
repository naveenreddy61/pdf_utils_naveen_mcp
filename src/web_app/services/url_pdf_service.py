"""URL-to-PDF-OCR service: headless browser capture → quality check → GenAI OCR."""

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pymupdf
from dotenv import load_dotenv

from pdf_utils.config import (
    UPLOAD_DIR,
    URL_PDF_BROWSER_TIMEOUT,
    URL_PDF_PRINT_WAIT_MS,
    URL_PDF_QUALITY_CHECK_ENABLED,
    URL_PDF_CHROMIUM_EXECUTABLE,
    OCR_MODEL,
)

load_dotenv()


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class UrlPdfOcrResult:
    url: str
    title: Optional[str]
    text: str
    page_count: int
    char_count: int
    word_count: int
    processing_time: float
    quality: str           # "GOOD" | "POOR" | "BLOCKED" | "UNKNOWN"
    quality_reason: str
    total_input_tokens: int
    total_output_tokens: int
    tokens_saved: int
    cached_pages: int
    llm_pages: int
    error: Optional[str] = None


# ── Popup / banner dismissal CSS ─────────────────────────────────────────────

_BANNER_HIDE_CSS = """
*[class*="cookie" i], *[class*="consent" i], *[class*="gdpr" i],
*[class*="banner" i], *[class*="popup" i], *[class*="modal" i],
*[class*="overlay" i], *[class*="interstitial" i],
*[id*="cookie" i], *[id*="consent" i], *[id*="gdpr" i],
*[id*="subscribe" i], *[id*="newsletter" i], *[id*="popup" i],
*[id*="modal" i], *[id*="paywall" i], *[id*="signup" i],
*[class*="paywall" i], *[class*="subscribe" i],
*[class*="sticky" i][style*="bottom"],
div[role="dialog"], div[role="alertdialog"],
div[aria-modal="true"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
body { overflow: visible !important; }
html { overflow: visible !important; }
"""

_AGGRESSIVE_BANNER_HIDE_CSS = _BANNER_HIDE_CSS + """
/* Aggressively hide ALL fixed/sticky overlays */
*[style*="position: fixed"], *[style*="position:fixed"],
*[style*="position: sticky"], *[style*="position:sticky"] {
    display: none !important;
}
"""

# Selectors for "accept" / "close" buttons on cookie/consent dialogs
_CONSENT_BUTTON_SELECTORS = [
    # Text-based (case insensitive via :i pseudo isn't standard, so we use JS)
    "button[id*='accept' i]", "button[id*='agree' i]", "button[id*='consent' i]",
    "button[class*='accept' i]", "button[class*='agree' i]",
    "a[id*='accept' i]", "a[class*='accept' i]",
    "[data-testid*='accept' i]", "[data-testid*='agree' i]",
    "#onetrust-accept-btn-handler",
    ".cc-btn.cc-allow", ".cc-accept", "#accept-cookies",
    "[aria-label*='Accept' i]", "[aria-label*='agree' i]",
]

_CLOSE_BUTTON_SELECTORS = [
    "button[aria-label*='close' i]", "button[aria-label*='dismiss' i]",
    "button[class*='close' i]", "button[class*='dismiss' i]",
    "[data-dismiss='modal']", ".modal-close", ".popup-close",
    "button[id*='close' i]",
]


# ── Playwright PDF capture ────────────────────────────────────────────────────

async def _capture_pdf_async(url: str, aggressive: bool = False) -> tuple[bytes, Optional[str]]:
    """
    Launch headless Chromium, navigate to URL, dismiss banners, print to PDF.
    Returns (pdf_bytes, page_title).
    """
    from playwright.async_api import async_playwright

    chromium_path = URL_PDF_CHROMIUM_EXECUTABLE or None
    # Auto-detect existing Playwright Chromium if default not available
    if not chromium_path:
        candidate = Path("/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome")
        if candidate.exists():
            chromium_path = str(candidate)

    banner_css = _AGGRESSIVE_BANNER_HIDE_CSS if aggressive else _BANNER_HIDE_CSS

    async with async_playwright() as p:
        launch_kwargs = {
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
            "headless": True,
        }
        if chromium_path:
            launch_kwargs["executable_path"] = chromium_path

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        page = await context.new_page()

        try:
            await page.goto(url, timeout=URL_PDF_BROWSER_TIMEOUT, wait_until="networkidle")
        except Exception:
            # Fallback: try with just domcontentloaded
            try:
                await page.goto(url, timeout=URL_PDF_BROWSER_TIMEOUT, wait_until="domcontentloaded")
                await asyncio.sleep(2)
            except Exception as e:
                await browser.close()
                raise RuntimeError(f"Could not load URL: {e}") from e

        title = await page.title()

        # ── Phase 1: Click consent / accept buttons ──────────────────────────
        for selector in _CONSENT_BUTTON_SELECTORS:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=300):
                    await el.click(timeout=500)
                    await asyncio.sleep(0.3)
                    break
            except Exception:
                pass

        # JS-based text matching for buttons that don't have obvious classes
        await page.evaluate("""() => {
            const acceptTexts = ['accept all', 'accept cookies', 'i accept', 'agree',
                                 'got it', 'ok, got it', 'allow all', 'allow cookies',
                                 'continue', 'proceed', 'i understand'];
            const buttons = [...document.querySelectorAll('button, a[role="button"]')];
            for (const btn of buttons) {
                const text = btn.textContent.trim().toLowerCase();
                if (acceptTexts.some(t => text === t || text.startsWith(t))) {
                    btn.click();
                    break;
                }
            }
        }""")
        await asyncio.sleep(0.5)

        # ── Phase 2: Scroll to reveal subscribe / sticky popups ──────────────
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
        await asyncio.sleep(URL_PDF_PRINT_WAIT_MS / 1000)

        # Click close buttons on any newly visible popups
        for selector in _CLOSE_BUTTON_SELECTORS:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=300):
                    await el.click(timeout=500)
                    await asyncio.sleep(0.3)
            except Exception:
                pass

        # Scroll back to top for clean print
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)

        # ── Phase 3: Inject CSS to hide remaining banners ────────────────────
        await page.add_style_tag(content=banner_css)
        await asyncio.sleep(0.2)

        # ── Phase 4: Print to PDF ────────────────────────────────────────────
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"},
        )

        await browser.close()
        return pdf_bytes, title or None


# ── LLM quality check ─────────────────────────────────────────────────────────

def _load_quality_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "url_pdf_quality_check.txt"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return (
            "Classify the following text as GOOD, POOR, or BLOCKED based on whether "
            "it contains real article content or is primarily cookie/consent/paywall noise.\n"
            "Reply: QUALITY: <GOOD|POOR|BLOCKED>\nREASON: <one sentence>\n\nText:\n"
        )


async def check_pdf_quality(pdf_bytes: bytes) -> tuple[str, str]:
    """
    Extract text from first 2 pages of the PDF and ask the LLM to assess quality.
    Returns (quality, reason) where quality is 'GOOD', 'POOR', or 'BLOCKED'.
    """
    if not URL_PDF_QUALITY_CHECK_ENABLED:
        return "UNKNOWN", "Quality check disabled."

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "UNKNOWN", "No API key configured for quality check."

    # Extract text from first 2 pages with PyMuPDF (fast, no API cost)
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages_to_check = min(2, len(doc))
        sample_text = ""
        for i in range(pages_to_check):
            sample_text += doc[i].get_text() + "\n"
        doc.close()
        sample_text = sample_text[:3000].strip()  # cap at 3000 chars
    except Exception:
        return "UNKNOWN", "Could not extract text for quality check."

    if len(sample_text) < 50:
        return "POOR", "Almost no text found on first pages — page may be image-only or empty."

    prompt = _load_quality_prompt()
    full_prompt = prompt + "\n" + sample_text

    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model=OCR_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=100,
                ),
            )
        )
        reply = response.text.strip() if response.text else ""

        # Parse reply
        quality = "UNKNOWN"
        reason = reply
        for line in reply.splitlines():
            if line.upper().startswith("QUALITY:"):
                val = line.split(":", 1)[1].strip().upper()
                if val in ("GOOD", "POOR", "BLOCKED"):
                    quality = val
            elif line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

        return quality, reason

    except Exception as e:
        return "UNKNOWN", f"Quality check failed: {e}"


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def extract_url_via_pdf_ocr(url: str) -> UrlPdfOcrResult:
    """
    Full pipeline: browser capture → quality check → OCR → result.
    """
    from web_app.services.ocr_service import process_document_async

    # Normalize URL
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url

    start = time.perf_counter()

    # Step 1: Capture PDF via headless browser
    try:
        pdf_bytes, title = await _capture_pdf_async(url, aggressive=False)
    except Exception as e:
        return UrlPdfOcrResult(
            url=url, title=None, text="", page_count=0,
            char_count=0, word_count=0,
            processing_time=time.perf_counter() - start,
            quality="UNKNOWN", quality_reason="",
            total_input_tokens=0, total_output_tokens=0,
            tokens_saved=0, cached_pages=0, llm_pages=0,
            error=f"Browser capture failed: {e}",
        )

    # Step 2: Quality check
    quality, quality_reason = await check_pdf_quality(pdf_bytes)

    # Step 3: Retry with aggressive banner removal if quality is poor
    if quality in ("POOR", "BLOCKED"):
        try:
            pdf_bytes_retry, _ = await _capture_pdf_async(url, aggressive=True)
            quality_retry, reason_retry = await check_pdf_quality(pdf_bytes_retry)
            if quality_retry == "GOOD" or quality_retry == "UNKNOWN":
                pdf_bytes = pdf_bytes_retry
                quality = quality_retry
                quality_reason = reason_retry + " (fixed via aggressive cleanup)"
            else:
                # Keep retry PDF anyway — it may still be better
                pdf_bytes = pdf_bytes_retry
                quality_reason = quality_reason + " [retry attempted]"
        except Exception:
            pass  # Keep original PDF

    # Step 4: Save PDF to temp file for OCR pipeline
    pdf_filename = f"url_pdf_{uuid.uuid4().hex[:8]}.pdf"
    pdf_path = UPLOAD_DIR / pdf_filename
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)

    try:
        # Get page count
        doc = pymupdf.open(str(pdf_path))
        page_count = len(doc)
        doc.close()

        if page_count == 0:
            pdf_path.unlink(missing_ok=True)
            return UrlPdfOcrResult(
                url=url, title=title, text="", page_count=0,
                char_count=0, word_count=0,
                processing_time=time.perf_counter() - start,
                quality=quality, quality_reason=quality_reason,
                total_input_tokens=0, total_output_tokens=0,
                tokens_saved=0, cached_pages=0, llm_pages=0,
                error="The captured PDF has no pages.",
            )

        # Step 5: Run OCR
        ocr_result = await process_document_async(pdf_path, 1, page_count)
        text = ocr_result.get("full_text", "")

        return UrlPdfOcrResult(
            url=url,
            title=title,
            text=text,
            page_count=page_count,
            char_count=len(text),
            word_count=len(text.split()),
            processing_time=time.perf_counter() - start,
            quality=quality,
            quality_reason=quality_reason,
            total_input_tokens=ocr_result.get("total_input_tokens", 0),
            total_output_tokens=ocr_result.get("total_output_tokens", 0),
            tokens_saved=ocr_result.get("tokens_saved", 0),
            cached_pages=ocr_result.get("cached_pages", 0),
            llm_pages=ocr_result.get("llm_pages", 0),
        )

    except Exception as e:
        return UrlPdfOcrResult(
            url=url, title=title, text="", page_count=0,
            char_count=0, word_count=0,
            processing_time=time.perf_counter() - start,
            quality=quality, quality_reason=quality_reason,
            total_input_tokens=0, total_output_tokens=0,
            tokens_saved=0, cached_pages=0, llm_pages=0,
            error=f"OCR processing failed: {e}",
        )
    finally:
        # Clean up temp PDF
        pdf_path.unlink(missing_ok=True)
