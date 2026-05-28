"""
自动解析器门面 (Auto Parser Facade)

PDF 解析策略:
- MinerU (AI云端): 配置后优先使用，精度高
- PyMuPDF (本地): 作为降级备选方案

门面职责:
- 统一入口，封装多个解析器的选择逻辑
- 根据后端配置自动选择合适的解析器
- 收集并汇总解析错误信息
"""
from __future__ import annotations

from pathlib import Path

from src.core.models import ParsedPaper
from src.infra.parsers.mineru_parser import MinerUStandardPDFParser
from src.infra.parsers.pymupdf_parser import PyMuPDFDocumentParser
from src.infra.parsers.shared import DocumentParseError
from src.infra.parsers.text_docx_parser import TextDocxDocumentParser


class LocalDocumentParser:
    """
    文档解析器门面类

    统一入口，根据文件类型和配置自动选择最佳解析策略:
    - .pdf: 尝试 MinerU (若配置) → 降级 PyMuPDF
    - .md/.docx: 直接使用 TextDocxDocumentParser
    """

    def __init__(
        self,
        *,
        backend: str = "auto",
        text_parser: TextDocxDocumentParser | None = None,
        mineru_parser: MinerUStandardPDFParser | None = None,
        pymupdf_parser: PyMuPDFDocumentParser | None = None,
    ) -> None:
        """
        初始化解析器门面

        Args:
            backend: 解析器后端选择
                     - "auto": MinerU 优先，PyMuPDF 备选
                     - "mineru"/"mineru-standard": 仅 MinerU
                     - "pymupdf"/"local": 仅 PyMuPDF
            text_parser: 文本解析器 (用于 MD/DOCX)
            mineru_parser: MinerU 解析器实例
            pymupdf_parser: PyMuPDF 解析器实例
        """
        self.backend = backend
        self.text_parser = text_parser or TextDocxDocumentParser()
        self.mineru_parser = mineru_parser
        self.pymupdf_parser = pymupdf_parser or PyMuPDFDocumentParser()

    def parse(self, path: Path) -> ParsedPaper:
        """
        解析文档入口

        Args:
            path: 文档文件路径

        Returns:
            ParsedPaper: 解析后的结构化论文对象

        Raises:
            DocumentParseError: 文件不存在或格式不支持
        """
        path = path.expanduser().resolve()
        if not path.exists():
            raise DocumentParseError(f"file does not exist: {path}")

        suffix = path.suffix.lower()
        # Markdown / DOCX 直接解析
        if suffix in TextDocxDocumentParser.SUPPORTED_EXTENSIONS:
            return self.text_parser.parse(path)
        # PDF 进入多策略解析流程
        if suffix == ".pdf":
            return self._parse_pdf(path)
        raise DocumentParseError(f"unsupported manuscript format: {suffix}")

    def _parse_pdf(self, path: Path) -> ParsedPaper:
        """
        PDF 多策略解析

        解析策略 (按顺序尝试):
        1. 若 backend 非 "pymupdf"/"local" 且 MinerU 已配置 → 尝试 MinerU
        2. 若 backend 包含 "auto"/"pymupdf"/"local" → 尝试 PyMuPDF

        Args:
            path: PDF 文件路径

        Returns:
            ParsedPaper: 解析后的论文对象

        Raises:
            DocumentParseError: 所有解析器均失败
        """
        errors: list[str] = []

        # 策略1: 尝试 MinerU (AI 云端解析)
        if self._should_try_mineru():
            try:
                return self._configured_mineru_parser().parse(path)
            except DocumentParseError as exc:
                errors.append(f"mineru-standard: {exc}")

        # 策略2: 尝试 PyMuPDF (本地备选)
        if self._should_try_pymupdf():
            try:
                return self.pymupdf_parser.parse(path)
            except DocumentParseError as exc:
                errors.append(f"pymupdf: {exc}")

        # 所有策略均失败
        if errors:
            raise DocumentParseError("PDF parsing failed; " + " | ".join(errors))
        raise DocumentParseError(f"no PDF parser available for backend: {self.backend}")

    def _should_try_mineru(self) -> bool:
        """
        判断是否应该尝试 MinerU

        MinerU 启用条件:
        - backend 不属于 {"pymupdf", "local"}
        - backend 属于 {"auto", "mineru", "mineru-standard"}
        - mineru_parser 已配置且 is_configured=True
        """
        backend = self.backend.lower()
        if backend in {"pymupdf", "local"}:
            return False
        if backend not in {"auto", "mineru", "mineru-standard"}:
            return False
        return bool(self.mineru_parser and self.mineru_parser.is_configured)

    def _should_try_pymupdf(self) -> bool:
        """
        判断是否应该尝试 PyMuPDF

        PyMuPDF 几乎总是启用 (除非要强制只用 MinerU)
        """
        backend = self.backend.lower()
        return backend in {"auto", "mineru", "mineru-standard", "pymupdf", "local"}

    def _configured_mineru_parser(self) -> MinerUStandardPDFParser:
        """
        获取已配置的 MinerU 解析器

        Returns:
            MinerUStandardPDFParser: 配置好的解析器实例

        Raises:
            DocumentParseError: MinerU 未配置
        """
        if not self.mineru_parser:
            raise DocumentParseError("MinerU parser is not configured")
        return self.mineru_parser
