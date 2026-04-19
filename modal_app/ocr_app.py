"""Modal deployment: serverless-GPU OCR endpoint.

Deploy:
    uv run modal deploy modal_app/ocr_app.py

The container loads the adapter selected by OCR_MODAL_MODEL_ID once at startup
(weights cached to a persistent Modal Volume, so cold starts only re-download
on the very first run). The endpoint accepts a base64-encoded PNG and returns
the extracted markdown.

Request:   POST {"image_base64": "<b64 PNG>"}
Response:  {"text": "...", "success": true, "model_id": "..."}
           {"text": "", "success": false, "error": "..."}
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import modal

# Make pdf_utils importable at deploy-time (this file runs locally during
# `modal deploy`, so we can read the active config values from there).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from pdf_utils.config import (  # noqa: E402
    OCR_MODAL_APP_NAME,
    OCR_MODAL_MODEL_ID,
    OCR_MODAL_GPU,
)

HF_CACHE_VOLUME_NAME = "pdf-ocr-hf-cache"
HF_CACHE_MOUNT = "/root/.cache/huggingface"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install(
        "torch==2.6.0",
        "torchvision",
        "transformers>=4.46.3",
        "Pillow",
        "einops",
        "sentencepiece",
        "flash-attn==2.7.3",
    )
    .add_local_dir(
        str(_REPO_ROOT / "modal_app"),
        remote_path="/root/modal_app",
        copy=True,
    )
    .env({"OCR_MODAL_MODEL_ID": OCR_MODAL_MODEL_ID})
)

hf_cache = modal.Volume.from_name(HF_CACHE_VOLUME_NAME, create_if_missing=True)

app = modal.App(name=OCR_MODAL_APP_NAME, image=image)


# Optional secret — uncomment the `secrets=[...]` line on the decorator below if
# you need to pass HF_TOKEN (e.g. for gated models) or other env into the
# container. Create it first:  modal secret create pdf-ocr-secrets HF_TOKEN=...
@app.cls(
    gpu=OCR_MODAL_GPU,
    timeout=600,
    scaledown_window=300,
    volumes={HF_CACHE_MOUNT: hf_cache},
    # secrets=[modal.Secret.from_name("pdf-ocr-secrets")],
)
class OCRModel:
    @modal.enter()
    def load(self):
        sys.path.insert(0, "/root")
        from modal_app.adapters import get_adapter

        model_id = os.environ["OCR_MODAL_MODEL_ID"]
        print(f"[ocr_app] Loading adapter for {model_id}")
        self.adapter = get_adapter(model_id)
        self.adapter.load()
        print(f"[ocr_app] Model ready: {model_id}")

    @modal.fastapi_endpoint(method="POST")
    def extract(self, request: dict) -> dict:
        import base64
        import io
        from PIL import Image

        image_b64 = request.get("image_base64", "")
        if not image_b64:
            return {"text": "", "success": False, "error": "No image_base64 provided"}

        try:
            pil_image = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
        except Exception as exc:
            return {"text": "", "success": False, "error": f"image decode: {exc}"}

        try:
            text = self.adapter.extract(pil_image)
            return {
                "text": text,
                "success": True,
                "model_id": self.adapter.MODEL_ID,
            }
        except Exception as exc:
            return {"text": "", "success": False, "error": f"inference: {exc}"}
