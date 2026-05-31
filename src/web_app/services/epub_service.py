"""EPUB extraction service — spine-first, semantics-aware."""

from pathlib import Path
from typing import Dict, List, Tuple
import base64
import io
import zipfile

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from PIL import Image

from pdf_utils.config import IMAGE_COMPRESSION_QUALITY, MIN_IMAGE_SIZE, MAX_IMAGES_PER_PAGE


# ── Internal helpers ──────────────────────────────────────────────────────────

def _open_book(file_path: Path) -> epub.EpubBook:
    return epub.read_epub(str(file_path), options={"ignore_ncx": False})


def _spine_docs(book: epub.EpubBook) -> List[epub.EpubHtml]:
    """Return XHTML spine items in reading order."""
    items = []
    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            items.append(item)
    return items


def _chapter_title(item: epub.EpubHtml, index: int) -> str:
    """Best-effort title from the first heading, or fall back to filename stem."""
    try:
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        h = soup.find(["h1", "h2", "h3"])
        if h:
            text = h.get_text(" ", strip=True)
            if text:
                return text
    except Exception:
        pass
    stem = Path(item.get_name()).stem
    return stem if stem else f"Chapter {index}"


def _xhtml_to_markdown(xhtml_bytes: bytes) -> str:
    """Convert XHTML to Markdown via pypandoc, with a BeautifulSoup fallback."""
    try:
        import pypandoc
        html = xhtml_bytes.decode("utf-8", errors="replace")
        return pypandoc.convert_text(
            html, "markdown", format="html", extra_args=["--wrap=none"]
        ).strip()
    except Exception:
        pass

    # Plain-text fallback using BeautifulSoup
    soup = BeautifulSoup(xhtml_bytes, "html.parser")
    body = soup.find("body") or soup
    lines = []
    for el in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        tag = el.name
        if tag == "h1":
            lines.append(f"# {text}")
        elif tag == "h2":
            lines.append(f"## {text}")
        elif tag == "h3":
            lines.append(f"### {text}")
        elif tag in ("h4", "h5", "h6"):
            lines.append(f"#### {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _flatten_toc(toc_items, level: int = 1) -> List[Tuple[int, str, str]]:
    """Flatten ebooklib's nested TOC to [(level, title, href)]."""
    result = []
    for item in toc_items:
        if isinstance(item, tuple):
            section, children = item
            if hasattr(section, "title") and section.title:
                result.append((level, section.title, getattr(section, "href", "")))
            result.extend(_flatten_toc(children, level + 1))
        elif hasattr(item, "title") and item.title:
            result.append((level, item.title, getattr(item, "href", "")))
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def get_epub_chapter_count(file_path: Path) -> int:
    """Number of XHTML spine items (chapters) in the EPUB."""
    book = _open_book(file_path)
    return len(_spine_docs(book))


def get_epub_metadata(file_path: Path) -> dict:
    """Dublin Core metadata fields."""
    book = _open_book(file_path)

    def _dc(field: str) -> str:
        values = book.get_metadata("DC", field)
        return values[0][0] if values else ""

    return {
        "title":       _dc("title"),
        "author":      _dc("creator"),
        "language":    _dc("language"),
        "publisher":   _dc("publisher"),
        "description": _dc("description"),
        "identifier":  _dc("identifier"),
        "rights":      _dc("rights"),
        "date":        _dc("date"),
    }


def get_epub_toc(file_path: Path) -> List[Tuple[int, str, int]]:
    """Table of contents as [(level, title, entry_number)].

    entry_number is a 1-based sequential counter used as a page-number surrogate
    so the existing toc_display() component can render it unchanged.
    """
    book = _open_book(file_path)
    flat = _flatten_toc(book.toc)
    return [(level, title, idx + 1) for idx, (level, title, _href) in enumerate(flat)]


def extract_epub_text(file_path: Path, start_ch: int, end_ch: int) -> str:
    """Extract spine items start_ch..end_ch (1-based) as combined Markdown."""
    book = _open_book(file_path)
    items = _spine_docs(book)
    start_ch = max(1, start_ch)
    end_ch = min(len(items), end_ch)

    parts = []
    for i in range(start_ch - 1, end_ch):
        item = items[i]
        title = _chapter_title(item, i + 1)
        md = _xhtml_to_markdown(item.get_body_content())
        parts.append(md if md else f"# {title}\n\n*(no content)*")

    return "\n\n---\n\n".join(parts)


def extract_epub_images(file_path: Path) -> Dict[int, List[dict]]:
    """Extract all images from the EPUB manifest.

    Returns {1: [{"data": "data:image/jpeg;base64,...", "filename": str, "raw_data": bytes}]}
    (single group keyed as 1, matching the page-keyed shape expected by the gallery component).
    """
    book = _open_book(file_path)
    images = []

    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        try:
            raw = item.get_content()
            if not raw:
                continue
            pil_img = Image.open(io.BytesIO(raw))
            w, h = pil_img.size
            if w < MIN_IMAGE_SIZE or h < MIN_IMAGE_SIZE:
                continue
            pil_img = pil_img.convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=IMAGE_COMPRESSION_QUALITY)
            compressed = buf.getvalue()
            stem = Path(item.get_name()).stem
            filename = f"{stem}.jpg"
            b64 = base64.b64encode(compressed).decode()
            images.append({
                "data":     f"data:image/jpeg;base64,{b64}",
                "filename": filename,
                "raw_data": compressed,
                "_area":    w * h,
            })
        except Exception:
            continue

    images.sort(key=lambda x: x["_area"], reverse=True)
    images = images[:MAX_IMAGES_PER_PAGE]
    for img in images:
        del img["_area"]

    return {1: images} if images else {}


def extract_epub_chapters_zip(file_path: Path) -> bytes:
    """Return ZIP bytes containing one .md file per spine item."""
    book = _open_book(file_path)
    items = _spine_docs(book)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, item in enumerate(items, 1):
            title = _chapter_title(item, i)
            md = _xhtml_to_markdown(item.get_body_content())
            safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)[:60].strip()
            fname = f"{i:02d}_{safe}.md"
            body = md if md else f"# {title}\n\n*(no content)*"
            zf.writestr(fname, f"{body}\n".encode("utf-8"))

    return buf.getvalue()
