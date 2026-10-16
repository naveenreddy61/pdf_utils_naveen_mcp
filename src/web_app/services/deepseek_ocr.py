"""DeepSeek V4.1 Flash vision OCR, used only for pages Gemini refuses to transcribe.

OpenAI-compatible Chat Completions API. Images go in the user message (a system
message carrying an image is a 400). Thinking is on by default at high effort;
it is disabled here for the same reason Gemini OCR runs at MINIMAL — transcription
is perception, and extra reasoning spends tokens second-guessing correct readings.
"""

import base64
import os
from typing import Tuple

import httpx

from pdf_utils.config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_OCR_MODEL,
    DEEPSEEK_OCR_MAX_TOKENS,
    DEEPSEEK_OCR_TIMEOUT,
)


def deepseek_api_key() -> str:
    """Read lazily: config is imported before ocr_service runs load_dotenv()."""
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


async def ocr_page_image_with_deepseek(png_bytes: bytes, prompt: str) -> Tuple[str, int, int]:
    """Transcribe one page image. Returns (text, input_tokens, output_tokens)."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    payload = {
        "model": DEEPSEEK_OCR_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": [
                {"type": "text", "text": "Transcribe this page."},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            ]},
        ],
        "max_tokens": DEEPSEEK_OCR_MAX_TOKENS,
        "thinking": {"type": "disabled"},
    }
    async with httpx.AsyncClient(timeout=DEEPSEEK_OCR_TIMEOUT) as http:
        resp = await http.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {deepseek_api_key()}"},
            json=payload,
        )
    resp.raise_for_status()
    data = resp.json()
    choice = data["choices"][0]
    text = choice["message"].get("content") or ""
    if not text.strip():
        raise ValueError(f"DeepSeek returned no text (finish_reason={choice.get('finish_reason')})")
    usage = data.get("usage") or {}
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
