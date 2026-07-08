"""Pandoc-based Markdown -> PDF conversion service (typst PDF engine)."""

import asyncio
import subprocess
import tempfile
from pathlib import Path

from pdf_utils.config import PANDOC_TIMEOUT, PANDOC_MAIN_FONT, PANDOC_MONO_FONT


async def convert_md_to_pdf_bytes(md_bytes: bytes, filename: str) -> bytes:
    """Save Markdown to a temp dir, convert to PDF via pandoc + typst, return PDF bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / filename
        src.write_bytes(md_bytes)
        pdf_path = tmp_path / (Path(filename).stem + ".pdf")

        result = await asyncio.to_thread(
            subprocess.run,
            [
                "pandoc", str(src), "-o", str(pdf_path),
                "--pdf-engine=typst",
                "-V", f"mainfont={PANDOC_MAIN_FONT}",
                "-V", f"monofont={PANDOC_MONO_FONT}",
                "--standalone",
            ],
            timeout=PANDOC_TIMEOUT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Pandoc conversion failed: {result.stderr}")

        if not pdf_path.exists():
            raise FileNotFoundError("Pandoc produced no output PDF")
        return pdf_path.read_bytes()
