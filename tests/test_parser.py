import tempfile
import unittest
from pathlib import Path

from src.infra.parser import DocumentParseError, LocalDocumentParser
from src.infra.parsers.shared import build_parsed_paper


class _DisabledMinerUParser:
    is_configured = False

    def parse(self, path: Path):  # pragma: no cover - should not be called
        raise AssertionError("disabled MinerU parser should not be called")


class _FailingPDFParser:
    is_configured = True

    def __init__(self, message: str) -> None:
        self.message = message

    def parse(self, path: Path):
        raise DocumentParseError(self.message)


class _SuccessfulPDFParser:
    def parse(self, path: Path):
        text = "Fallback PDF Title\n\nAbstract\nFallback abstract.\n\n1 Introduction\nBody text."
        return build_parsed_paper(path, text, [text])


class ParserTests(unittest.TestCase):
    def test_text_parser_extracts_title_and_abstract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.txt"
            path.write_text(
                "A Strong Paper Title\n\nAbstract\nThis is the abstract.\n\n1 Introduction\nBody text.",
                encoding="utf-8",
            )
            parsed = LocalDocumentParser().parse(path)

            self.assertEqual(parsed.title, "A Strong Paper Title")
            self.assertIn("abstract", parsed.abstract.lower())
            self.assertGreaterEqual(len(parsed.sections), 1)

    def test_pdf_uses_pymupdf_fallback_when_mineru_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(b"%PDF fake")
            parser = LocalDocumentParser(
                backend="auto",
                mineru_parser=_DisabledMinerUParser(),
                pymupdf_parser=_SuccessfulPDFParser(),
            )
            parsed = parser.parse(path)

        self.assertEqual(parsed.title, "Fallback PDF Title")

    def test_pdf_falls_back_to_pymupdf_when_mineru_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(b"%PDF fake")
            parser = LocalDocumentParser(
                backend="auto",
                mineru_parser=_FailingPDFParser("MinerU failed"),
                pymupdf_parser=_SuccessfulPDFParser(),
            )
            parsed = parser.parse(path)

        self.assertEqual(parsed.title, "Fallback PDF Title")

    def test_pdf_returns_failure_when_all_pdf_parsers_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(b"%PDF fake")
            parser = LocalDocumentParser(
                backend="auto",
                mineru_parser=_FailingPDFParser("MinerU failed"),
                pymupdf_parser=_FailingPDFParser("PyMuPDF failed"),
            )

            with self.assertRaises(DocumentParseError) as exc:
                parser.parse(path)

        self.assertIn("mineru-standard: MinerU failed", str(exc.exception))
        self.assertIn("pymupdf: PyMuPDF failed", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
