"""
文档解析器模块 - 提供统一的文档解析入口

职责:
1. 根据配置选择合适的解析器后端
2. 构建并返回 LocalDocumentParser 门面实例

架构设计:
- LocalDocumentParser 是门面 (Facade)，封装了多种解析器实现
- 支持: MinerU (云端 AI 解析) / PyMuPDF (本地解析) / TextParser (Markdown/DOCX)
"""
from __future__ import annotations

from src.infra.parsers import DocumentParseError, LocalDocumentParser
from src.infra.parsers.mineru_parser import MinerUStandardPDFParser
from src.infra.parsers.pymupdf_parser import PyMuPDFDocumentParser
from src.infra.settings import Settings


def build_document_parser(settings: Settings) -> LocalDocumentParser:
    """
    根据配置构建文档解析器实例

    构建流程:
    1. 创建 PyMuPDFDocumentParser (本地 PDF 解析器，始终创建)
    2. 创建 MinerUStandardPDFParser (云端 AI 解析器，按需创建)
    3. 创建 LocalDocumentParser 门面，聚合上述解析器

    Args:
        settings: 应用程序配置对象

    Returns:
        LocalDocumentParser: 统一的文档解析门面
    """
    return LocalDocumentParser(
        backend=settings.parser_backend,           # 解析器后端选择: auto / mineru / pymupdf / local
        mineru_parser=MinerUStandardPDFParser(    # 云端 AI 解析器 (如已配置 API Token)
            token=settings.mineru_api_token,
            base_url=settings.mineru_base_url,
            model_version=settings.mineru_model_version,
            timeout_sec=settings.mineru_timeout_sec,
            poll_interval_sec=settings.mineru_poll_interval_sec,
            request_timeout_sec=settings.mineru_request_timeout_sec,
        ),
        pymupdf_parser=PyMuPDFDocumentParser(),   # 本地 PDF 解析器 (备选方案)
    )


__all__ = ["DocumentParseError", "LocalDocumentParser", "build_document_parser"]
