from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


_NEW_ARXIV_ID_PATTERN = re.compile(r"\d{4}\.\d{4,5}(?:v\d+)?")
_OLD_ARXIV_ID_PATTERN = re.compile(r"[A-Za-z.-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?")


class PaperSourceFetchError(RuntimeError):
    pass


class PaperSourceTooLargeError(PaperSourceFetchError):
    pass


@dataclass(frozen=True)
class FetchedPaper:
    paper_path: str
    filename: str
    source_url: str
    pdf_url: str
    arxiv_id: str
    size_bytes: int


def fetch_arxiv_pdf(arxiv_input: str, *, uploads_dir: Path, max_bytes: int, timeout_seconds: int = 30) -> FetchedPaper:
    arxiv_id = normalize_arxiv_id(arxiv_input)
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    request = Request(pdf_url, headers={"User-Agent": "paper-review-agent/0.1"})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            content = _read_limited_response(response, max_bytes=max_bytes)
    except PaperSourceFetchError:
        raise
    except HTTPError as exc:
        raise PaperSourceFetchError(f"arXiv PDF fetch failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise PaperSourceFetchError(f"arXiv PDF fetch failed: {exc.reason}") from exc
    except OSError as exc:
        raise PaperSourceFetchError(f"arXiv PDF fetch failed: {exc}") from exc

    if not content.startswith(b"%PDF"):
        raise PaperSourceFetchError("arXiv did not return a PDF document")

    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_arxiv_{_safe_arxiv_filename(arxiv_id)}.pdf"
    target = uploads_dir / filename
    target.write_bytes(content)
    return FetchedPaper(
        paper_path=str(target),
        filename=filename,
        source_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=pdf_url,
        arxiv_id=arxiv_id,
        size_bytes=len(content),
    )


def normalize_arxiv_id(arxiv_input: str) -> str:
    value = arxiv_input.strip()
    if not value:
        raise PaperSourceFetchError("arXiv id or URL is required")

    value = re.sub(r"^arxiv:\s*", "", value, flags=re.IGNORECASE).strip()
    parsed = urlparse(value)
    if parsed.netloc:
        if parsed.netloc.lower() not in {"arxiv.org", "www.arxiv.org"}:
            raise PaperSourceFetchError("only arxiv.org abs/pdf URLs are supported")
        path = parsed.path.strip("/")
        if path.startswith(("abs/", "pdf/")):
            value = path.split("/", 1)[1]
        else:
            raise PaperSourceFetchError("only arxiv.org abs/pdf URLs are supported")

    value = value.split("?", 1)[0].split("#", 1)[0].strip().strip("/")
    if value.endswith(".pdf"):
        value = value[:-4]

    if _NEW_ARXIV_ID_PATTERN.fullmatch(value) or _OLD_ARXIV_ID_PATTERN.fullmatch(value):
        return value
    raise PaperSourceFetchError(f"invalid arXiv id: {arxiv_input}")


def _read_limited_response(response, *, max_bytes: int) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise PaperSourceTooLargeError(f"arXiv PDF is too large: max {max_bytes} bytes")

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PaperSourceTooLargeError(f"arXiv PDF is too large: max {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _safe_arxiv_filename(arxiv_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", arxiv_id).strip("._") or "paper"
