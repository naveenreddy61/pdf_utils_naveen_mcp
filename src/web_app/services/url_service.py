"""URL-to-Markdown extraction service using trafilatura."""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class UrlExtractionResult:
    url: str
    title: str | None
    markdown: str
    char_count: int
    word_count: int
    processing_time: float
    error: str | None = None


def _extract_sync(
    url: str,
    include_links: bool,
    include_images: bool,
    include_tables: bool,
) -> UrlExtractionResult:
    """Synchronous extraction – runs in a thread pool."""
    import trafilatura

    start = time.perf_counter()

    # Fetch
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return UrlExtractionResult(
            url=url, title=None, markdown="",
            char_count=0, word_count=0,
            processing_time=time.perf_counter() - start,
            error="Could not fetch the URL. Check the address and try again.",
        )

    # Extract
    result = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=include_links,
        include_images=include_images,
        include_tables=include_tables,
        favor_recall=True,
        with_metadata=True,
    )

    if not result:
        return UrlExtractionResult(
            url=url, title=None, markdown="",
            char_count=0, word_count=0,
            processing_time=time.perf_counter() - start,
            error="No main content could be extracted from this page.",
        )

    # trafilatura returns metadata as part of the string when with_metadata=True
    # Re-extract without metadata for clean markdown, and separately get title
    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata else None

    raw_md = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=include_links,
        include_images=include_images,
        include_tables=include_tables,
        favor_recall=True,
        with_metadata=False,
    ) or ""

    # Remove excessive blank lines (3+ → 2) and trailing spaces
    import re
    clean_md = re.sub(r'\n{3,}', '\n\n', raw_md)
    clean_md = re.sub(r'[ \t]+\n', '\n', clean_md).strip()

    elapsed = time.perf_counter() - start
    return UrlExtractionResult(
        url=url,
        title=title,
        markdown=clean_md,
        char_count=len(clean_md),
        word_count=len(clean_md.split()),
        processing_time=elapsed,
    )


async def extract_url_to_markdown(
    url: str,
    include_links: bool = True,
    include_images: bool = False,
    include_tables: bool = True,
) -> UrlExtractionResult:
    """Async wrapper – runs blocking trafilatura in a thread."""
    # Normalise URL
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url

    return await asyncio.to_thread(
        _extract_sync, url, include_links, include_images, include_tables
    )
