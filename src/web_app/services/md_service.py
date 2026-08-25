"""Markdown -> PDF conversion via vendored md-render-pipeline/render.sh."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import tempfile
from pathlib import Path

from pdf_utils.config import (
    MAX_MD_SIZE_BYTES,
    MAX_MD_SIZE_MB,
    MD_RENDER_SCRIPT,
    MD_RENDER_TIMEOUT,
)
from web_app.core.utils import sanitize_filename

_SENTINELS = ("pyproject.toml", ".git")
_STDERR_LIMIT = 2000


def _project_root(start: Path | None = None) -> Path:
    """Repo root: first ancestor of start (or this file) with pyproject.toml or .git.

    Stops at that sentinel so a missing vendored copy cannot pick a sibling
    directory such as /root/projects/md-render-pipeline.
    """
    here = Path(start) if start is not None else Path(__file__).resolve()
    for parent in here.parents:
        if any((parent / name).exists() for name in _SENTINELS):
            return parent
    parents = list(here.parents)
    return parents[3] if len(parents) > 3 else parents[-1]


def resolve_render_script(start: Path | None = None) -> Path:
    override = (MD_RENDER_SCRIPT or "").strip()
    if override:
        return Path(override)
    return _project_root(start) / "md-render-pipeline" / "render.sh"


def _truncate_stderr(text: str) -> str:
    if not text:
        return "no error output"
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= _STDERR_LIMIT:
        return collapsed
    return collapsed[-_STDERR_LIMIT:] + " … (truncated)"


def _run_render(
    render_sh: Path, src: Path, pdf_path: Path, tmp_path: Path
) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(
        [str(render_sh), str(src), str(pdf_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        cwd=str(tmp_path),
    )
    try:
        stdout, stderr = proc.communicate(timeout=MD_RENDER_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(
            f"[md_service] render.sh timed out after {MD_RENDER_TIMEOUT}s",
            flush=True,
        )
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
        raise
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def _convert_md_to_pdf_bytes_sync(md_bytes: bytes, filename: str) -> bytes:
    if len(md_bytes) > MAX_MD_SIZE_BYTES:
        raise RuntimeError(
            f"Markdown is too large (max {MAX_MD_SIZE_MB} MB)."
        )

    render_sh = resolve_render_script()
    if not render_sh.is_file():
        raise RuntimeError(
            f"Markdown renderer not found at {render_sh}. "
            "Set MD_RENDER_SCRIPT or vendor md-render-pipeline/."
        )
    if not os.access(render_sh, os.X_OK):
        raise RuntimeError(f"Markdown renderer is not executable: {render_sh}")

    safe_name = sanitize_filename(filename)
    stem = Path(safe_name).stem or "input"
    src_name = stem + ".md"
    pdf_name = stem + ".pdf"

    with tempfile.TemporaryDirectory(prefix="md-render-") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / src_name
        pdf_path = tmp_path / pdf_name
        src.write_bytes(md_bytes)

        try:
            result = _run_render(render_sh, src, pdf_path, tmp_path)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Markdown conversion timed out after {MD_RENDER_TIMEOUT} seconds."
            ) from None

        if result.returncode != 0:
            print(
                f"[md_service] render.sh failed rc={result.returncode}\n"
                f"{result.stderr}",
                flush=True,
            )
            raise RuntimeError(
                "Markdown conversion failed: " + _truncate_stderr(result.stderr)
            )
        if result.stderr:
            print(f"[md_service] render.sh stderr:\n{result.stderr}", flush=True)

        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise FileNotFoundError("Markdown renderer produced no output PDF")
        data = pdf_path.read_bytes()
        if not data.startswith(b"%PDF"):
            raise RuntimeError("Markdown renderer produced a non-PDF file")
        return data


async def convert_md_to_pdf_bytes(md_bytes: bytes, filename: str) -> bytes:
    """Save Markdown to a temp dir, convert via render.sh, return PDF bytes."""
    return await asyncio.to_thread(_convert_md_to_pdf_bytes_sync, md_bytes, filename)
