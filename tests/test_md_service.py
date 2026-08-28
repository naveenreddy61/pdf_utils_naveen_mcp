"""Markdown → PDF conversion via vendored md-render-pipeline/render.sh."""

from pathlib import Path
import asyncio
import os
import shutil
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from web_app.services.md_service import (
    _project_root,
    convert_md_to_pdf_bytes,
    resolve_render_script,
)
from pdf_utils.config import MAX_MD_SIZE_BYTES

FIXTURE = r"""# Pipeline check

| Col A | Col B |
|-------|-------|
| foo   | bar   |

Inline math $x^2$ and a display:

$$
a^2 + b^2 = c^2
$$

Sample mean $\bar{x}$ and $\overline{A}$:

$$
\bar{x} = \frac{1}{R}\sum_{r=1}^{R} X_r
$$
"""


def _skip(reason: str) -> None:
    print(f"skip: {reason}")


def test_convert_md_to_pdf_bytes_table_and_math() -> None:
    script = resolve_render_script()
    if not script.is_file() or not os.access(script, os.X_OK):
        _skip(f"render.sh missing or not executable ({script})")
        return
    if shutil.which("pandoc") is None or shutil.which("typst") is None:
        _skip("pandoc or typst not on PATH")
        return

    pdf = asyncio.run(convert_md_to_pdf_bytes(FIXTURE.encode(), "fixture.md"))
    assert pdf.startswith(b"%PDF"), pdf[:20]
    assert len(pdf) > 0

    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        assert doc.page_count >= 1
        text = "".join(page.get_text() for page in doc)
        assert "\u0304" in text, "expected TeX-style bar (macron) on \\bar{x}"
        assert "\u203e" not in text, "Pandoc superscript overline leaked into PDF"
    finally:
        doc.close()
    print("ok: table+math PDF")


def test_convert_md_rejects_oversize() -> None:
    blob = b"x" * (MAX_MD_SIZE_BYTES + 1)
    try:
        asyncio.run(convert_md_to_pdf_bytes(blob, "huge.md"))
    except RuntimeError as exc:
        assert "too large" in str(exc).lower()
        print("ok: oversize rejected")
        return
    raise AssertionError("expected RuntimeError for oversize markdown")


def test_resolve_render_script_finds_vendored_copy() -> None:
    script = resolve_render_script()
    if not script.is_file():
        _skip(f"pipeline not vendored at {script}")
        return
    assert script.name == "render.sh"
    print(f"ok: vendored script {script}")


def test_project_root_does_not_escape_to_sibling(tmp_root: Path | None = None) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        repo = base / "repo"
        decoy = base / "md-render-pipeline"
        decoy.mkdir()
        (decoy / "render.sh").write_text("#!/bin/sh\necho decoy\n")
        services = repo / "src" / "web_app" / "services"
        services.mkdir(parents=True)
        (repo / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        fake = services / "md_service.py"
        fake.write_text("")

        root = _project_root(fake)
        assert root == repo, root
        chosen = resolve_render_script(fake)
        assert chosen == repo / "md-render-pipeline" / "render.sh", chosen
        assert chosen != decoy / "render.sh"
    print("ok: sibling pipeline not selected")


def test_auto_download_script_local_and_gcs() -> None:
    from fasthtml.common import to_xml
    from web_app.ui.components import auto_download_script
    from web_app.services.gcs_service import content_disposition_attachment

    local = to_xml(auto_download_script("abc_note.pdf", "note.pdf"))
    assert "/abc_note.pdf" in local
    assert "a.download" in local
    assert "iframe" not in local

    gcs = to_xml(auto_download_script(
        "abc_note.pdf", "note.pdf",
        href="https://storage.googleapis.com/bucket/temp-downloads/x.pdf?X-Goog-Signature=abc",
    ))
    assert "storage.googleapis.com" in gcs
    assert "iframe" in gcs
    assert "/abc_note.pdf" not in gcs
    assert content_disposition_attachment("My Note!.pdf") == (
        'attachment; filename="My_Note_.pdf"'
    )
    print("ok: auto-download script local vs GCS")


def main() -> int:
    failed = 0
    for fn in (
        test_project_root_does_not_escape_to_sibling,
        test_resolve_render_script_finds_vendored_copy,
        test_convert_md_rejects_oversize,
        test_convert_md_to_pdf_bytes_table_and_math,
        test_auto_download_script_local_and_gcs,
    ):
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
    if failed:
        print(f"{failed} test(s) failed")
        return 1
    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
