from src.infra.parsers.auto_parser import LocalDocumentParser
from src.infra.parsers.mineru_parser import MinerUStandardPDFParser
from src.infra.parsers.pymupdf_parser import PyMuPDFDocumentParser
from src.infra.parsers.shared import DocumentParseError
from src.infra.parsers.text_docx_parser import TextDocxDocumentParser

__all__ = [
    "DocumentParseError",
    "LocalDocumentParser",
    "MinerUStandardPDFParser",
    "PyMuPDFDocumentParser",
    "TextDocxDocumentParser",
]

'''
# 这里我注释写一个解析逻辑
# 首先，我们runtime里面会调用这个 parser = build_document_parser(settings)
然后这个会有一个统一的入口 LocalDocumentParser
然后这个 LocalDocumentParser 会根据不同的文件类型和配置选择不同的解析器
- 如果是 PDF 文件，它会优先尝试使用 MinerU 解析器（如果配置了 MinerU 的 API Token），如果 MinerU 解析失败或未配置，它会降级使用 PyMuPDF 解析器。
- 如果是 Markdown 或 DOCX 文件，它会直接使用 TextDocxDocumentParser 进行解析。
# 这个设计模式叫做门面模式（Facade Pattern），它提供了一个统一的接口来封装多个解析器的选择逻辑，使得调用者不需要关心具体的解析器实现细节，只需要调用统一的 parse 方法即可。
# 这样做的好处是提高了代码的可维护性和可扩展性，如果将来需要增加新的解析器，只需要在 LocalDocumentParser 中添加新的解析器实现，而不需要修改调用者的代码。
# 另外，LocalDocumentParser 还会收集并汇总  解析错误信息，确保在解析过程中出现问题时，能够提供有用的错误信息给调用者。



'''