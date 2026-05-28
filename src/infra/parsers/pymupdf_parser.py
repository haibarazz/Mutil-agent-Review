from __future__ import annotations

from pathlib import Path

from src.core.models import ParsedPaper
from src.infra.parsers.shared import DocumentParseError, build_parsed_paper


class PyMuPDFDocumentParser:
    name = "pymupdf"

    def parse(self, path: Path) -> ParsedPaper:
        path = path.expanduser().resolve()
        if not path.exists():
            raise DocumentParseError(f"file does not exist: {path}")
        if path.suffix.lower() != ".pdf":
            raise DocumentParseError(f"PyMuPDF only supports PDF files: {path.suffix}")

        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise DocumentParseError("PyMuPDF is required for PDF parsing") from exc

        pages: list[str] = []
        try:
            with fitz.open(path) as doc:
                for page in doc:
                    pages.append(page.get_text("text"))
        except Exception as exc:
            raise DocumentParseError(f"PyMuPDF failed to parse PDF: {exc}") from exc

        return build_parsed_paper(path, "\n\n".join(pages), pages)
