"""LibreOffice-based PPTX/PPT → PDF conversion service."""

import asyncio
import subprocess
import tempfile
from pathlib import Path

from pdf_utils.config import LIBREOFFICE_TIMEOUT


async def convert_pptx_to_pdf_bytes(pptx_bytes: bytes, filename: str) -> bytes:
    """Save PPTX/PPT to a temp dir, convert to PDF via LibreOffice, return PDF bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / filename
        src.write_bytes(pptx_bytes)

        result = await asyncio.to_thread(
            subprocess.run,
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
            timeout=LIBREOFFICE_TIMEOUT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

        pdf_path = tmp_path / (Path(filename).stem + ".pdf")
        if not pdf_path.exists():
            raise FileNotFoundError("LibreOffice produced no output PDF")
        return pdf_path.read_bytes()
