"""OCR model adapters for the Modal GPU endpoint.

Each adapter encapsulates how to load a specific model and how to extract text
from a PIL image. Add a new adapter + register it in ADAPTERS to support a new
model. Remember to extend the Modal image in ocr_app.py with any deps the new
adapter needs (e.g., llama-cpp-python for GGUF variants).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OCRAdapter(Protocol):
    MODEL_ID: str

    def load(self) -> None:
        """Load weights. Called once per container via @modal.enter()."""
        ...

    def extract(self, pil_image) -> str:
        """Run OCR on a single PIL image. Returns markdown string."""
        ...


class DeepSeekOCR2Adapter:
    MODEL_ID = "deepseek-ai/DeepSeek-OCR-2"
    PROMPT = (
        "<image>\n"
        "Convert the document to markdown. "
        "Extract all text accurately. "
        "Use LaTeX enclosed in $ or $$ for mathematical expressions. "
        "Describe images/figures as [Figure: description]. "
        "Preserve document structure."
    )

    def load(self) -> None:
        from transformers import AutoModel, AutoTokenizer
        import torch

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_ID,
            trust_remote_code=True,
        )
        self.model = (
            AutoModel.from_pretrained(
                self.MODEL_ID,
                trust_remote_code=True,
                use_safetensors=True,
                _attn_implementation="flash_attention_2",
            )
            .eval()
            .cuda()
            .to(torch.bfloat16)
        )

    def extract(self, pil_image) -> str:
        return self.model.chat(self.tokenizer, [pil_image], self.PROMPT)


ADAPTERS: dict[str, type] = {
    DeepSeekOCR2Adapter.MODEL_ID: DeepSeekOCR2Adapter,
}


def get_adapter(model_id: str) -> OCRAdapter:
    """Return an (unloaded) adapter instance for the given model ID."""
    if model_id not in ADAPTERS:
        raise ValueError(
            f"No adapter registered for model_id={model_id!r}. "
            f"Known: {sorted(ADAPTERS)}"
        )
    return ADAPTERS[model_id]()
