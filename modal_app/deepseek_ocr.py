"""
Modal deployment for DeepSeek OCR 2.

Deploy with:
    modal deploy modal_app/deepseek_ocr.py

The deployment exposes a POST endpoint that accepts a base64-encoded page image
and returns the extracted markdown text.

Endpoint URL after deployment:
    https://deepseek-ocr-service--deepseekocr-extract.modal.run

Request body:
    {"image_base64": "<base64-encoded PNG bytes>"}

Response:
    {"text": "<extracted markdown>", "success": true}
    {"text": "", "success": false, "error": "<message>"}
"""

import modal

# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")  # OpenCV / PIL deps
    .pip_install(
        "torch==2.6.0",
        "torchvision",
        "transformers>=4.46.3",
        "Pillow",
        "einops",
        "sentencepiece",
        # flash-attn speeds up attention on Ampere+ GPUs (A100 / H100)
        "flash-attn==2.7.3",
    )
)

app = modal.App(name="deepseek-ocr-service", image=image)

# ---------------------------------------------------------------------------
# Model class — loaded once per container, reused across requests
# ---------------------------------------------------------------------------

@app.cls(
    gpu="A100",
    image=image,
    timeout=300,               # max seconds a single request may run
    container_idle_timeout=300,  # keep container warm for 5 min after last request
    secrets=[modal.Secret.from_name("deepseek-ocr-secrets", required=False)],
)
class DeepSeekOCR:
    """Wraps DeepSeek-OCR-2 and exposes it as an HTTP endpoint on Modal."""

    @modal.enter()
    def load_model(self):
        """Load model and tokenizer once when the container starts."""
        from transformers import AutoModel, AutoTokenizer
        import torch

        model_name = "deepseek-ai/DeepSeek-OCR-2"
        print(f"Loading {model_name} …")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_safetensors=True,
            _attn_implementation="flash_attention_2",
        ).eval().cuda().to(torch.bfloat16)

        print("Model ready.")

    @modal.fastapi_endpoint(method="POST")
    def extract(self, request: dict) -> dict:
        """
        Extract text from a single page image.

        Args:
            request: {"image_base64": "<base64 PNG bytes>"}

        Returns:
            {"text": "<markdown>", "success": True}
            or {"text": "", "success": False, "error": "<msg>"}
        """
        import base64
        import io
        from PIL import Image

        image_b64 = request.get("image_base64", "")
        if not image_b64:
            return {"text": "", "success": False, "error": "No image_base64 provided"}

        try:
            image_bytes = base64.b64decode(image_b64)
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            return {"text": "", "success": False, "error": f"Image decode error: {exc}"}

        try:
            prompt = (
                "<image>\n"
                "Convert the document to markdown. "
                "Extract all text accurately. "
                "Use LaTeX enclosed in $ or $$ for mathematical expressions. "
                "Describe images/figures as [Figure: description]. "
                "Preserve document structure."
            )
            result = self.model.chat(self.tokenizer, [pil_image], prompt)
            return {"text": result, "success": True}
        except Exception as exc:
            return {"text": "", "success": False, "error": f"Inference error: {exc}"}
