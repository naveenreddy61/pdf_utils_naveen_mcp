"""Download a PDF that lives behind a direct link, server-side.

Given something like
`https://www.nber.org/system/files/working_papers/w35559/w35559.pdf`, fetch the
bytes here rather than asking the user to download and re-upload them. The
result is handed to the ordinary upload task, so the file is indistinguishable
from one that arrived through the file picker.

Two things this module is careful about:

* **It verifies the bytes, not the URL.** A `.pdf` suffix proves nothing — a
  paywall or a login wall happily returns HTML at that address — so the check
  is the `%PDF-` magic number on what actually came back.
* **It refuses to fetch private addresses.** This is a URL the *server*
  dereferences on a user's behalf, which is the classic SSRF shape: without a
  check, `http://169.254.169.254/...` or `http://localhost:8000/` would be
  reachable from the public web through this box.
"""

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from pdf_utils.config import (
    PDF_URL_FETCH_TIMEOUT,
    PDF_URL_MAX_REDIRECTS,
    PDF_URL_USER_AGENT,
)

_PDF_MAGIC = b"%PDF-"


@dataclass
class PdfDownloadResult:
    url: str
    content: bytes = b""
    filename: str = "download.pdf"
    processing_time: float = 0.0
    error: str | None = None


def normalize_url(url: str) -> str:
    """Add a scheme if the user pasted a bare host."""
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _filename_from(url: str, content_disposition: str | None) -> str:
    """Best available name for the downloaded file, always ending in .pdf."""
    name = ""
    if content_disposition:
        # Good enough for the `filename="x.pdf"` / `filename=x.pdf` forms that
        # servers actually send; RFC 5987 `filename*` is not worth parsing here.
        for part in content_disposition.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                name = part[len("filename="):].strip().strip('"')
                break

    if not name:
        name = unquote(urlparse(url).path.rsplit("/", 1)[-1])

    name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        name = "download"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _is_public_host(hostname: str) -> bool:
    """True when every address the host resolves to is publicly routable.

    Resolving here and again inside httpx is a small TOCTOU window, and closing
    it properly would mean pinning the connection to a checked IP. For a
    single-user utility the cheap check is the right trade; the expensive one
    would still not stop a redirect chain we did not follow ourselves — which is
    why redirects are followed manually below, with this run on each hop.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


async def download_pdf_from_url(url: str, max_bytes: int) -> PdfDownloadResult:
    """Fetch a PDF over HTTP(S) into memory.

    Redirects are followed by hand so each hop's host can be re-checked, and the
    body is streamed so an oversized (or endless) response is cut off instead of
    filling memory first and being rejected after.
    """
    import httpx

    start = time.perf_counter()
    url = normalize_url(url)

    def fail(msg: str) -> PdfDownloadResult:
        return PdfDownloadResult(url=url, processing_time=time.perf_counter() - start,
                                 error=msg)

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return fail("Enter a full http:// or https:// link to a PDF.")

    headers = {"User-Agent": PDF_URL_USER_AGENT, "Accept": "application/pdf,*/*"}
    timeout = httpx.Timeout(PDF_URL_FETCH_TIMEOUT, connect=15.0)

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=timeout,
                                     headers=headers) as client:
            current = url
            for _ in range(PDF_URL_MAX_REDIRECTS + 1):
                host = urlparse(current).hostname or ""
                if not await asyncio.to_thread(_is_public_host, host):
                    return fail(
                        f"Refusing to fetch “{host}” — it is not a public address."
                    )

                async with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location", "")
                        if not location:
                            return fail("The server sent a redirect with no target.")
                        current = str(response.url.join(location))
                        continue

                    if response.status_code >= 400:
                        return fail(
                            f"The server returned HTTP {response.status_code}. "
                            "The link may be paywalled, expired, or wrong."
                        )

                    declared = response.headers.get("content-length")
                    if declared and int(declared) > max_bytes:
                        return fail(
                            f"That PDF is {int(declared) / 1024 / 1024:.0f} MB — "
                            f"over the {max_bytes // 1024 // 1024} MB limit."
                        )

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            return fail(
                                f"That file is larger than the "
                                f"{max_bytes // 1024 // 1024} MB limit."
                            )
                        chunks.append(chunk)

                    content = b"".join(chunks)
                    if not content:
                        return fail("The server returned an empty response.")
                    # The extension lies often enough that this is the real test.
                    if not content.startswith(_PDF_MAGIC):
                        ctype = response.headers.get("content-type", "unknown")
                        return fail(
                            f"That link did not return a PDF (content-type: {ctype}). "
                            "It may be a landing or login page rather than the file."
                        )

                    return PdfDownloadResult(
                        url=str(response.url),
                        content=content,
                        filename=_filename_from(
                            str(response.url),
                            response.headers.get("content-disposition"),
                        ),
                        processing_time=time.perf_counter() - start,
                    )

            return fail("Too many redirects.")

    except httpx.TimeoutException:
        return fail(f"The download timed out after {PDF_URL_FETCH_TIMEOUT}s.")
    except httpx.HTTPError as exc:
        return fail(f"Could not reach that URL: {exc}")
