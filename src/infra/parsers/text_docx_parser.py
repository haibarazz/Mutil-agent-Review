from __future__ import annotations

from pathlib import Path

from src.core.models import ParsedPaper
from src.infra.parsers.shared import DocumentParseError, build_parsed_paper


class TextDocxDocumentParser:
    TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".tex"}
    SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".docx"}

    def parse(self, path: Path) -> ParsedPaper:
        path = path.expanduser().resolve()
        if not path.exists():
            raise DocumentParseError(f"file does not exist: {path}")

        suffix = path.suffix.lower()
        if suffix in self.TEXT_EXTENSIONS:
            text = self._read_text(path)
            pages = [text]
        elif suffix == ".docx":
            text, pages = self._read_docx(path)
        else:
            raise DocumentParseError(f"unsupported text/docx manuscript format: {suffix}")

        return build_parsed_paper(path, text, pages)

    def _read_text(self, path: Path) -> str:
        raw = path.read_bytes()
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    def _read_docx(self, path: Path) -> tuple[str, list[str]]:
        try:
            from docx import Document  # type: ignore
        except ImportError as exc:
            raise DocumentParseError("python-docx is required for DOCX parsing") from exc

        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
        return text, [text]
