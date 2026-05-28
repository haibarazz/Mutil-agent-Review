"""文档解析节点 - v3.0 将上传的论文文件解析为纯文本，增加parse_error输出"""
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from utils.file.file import FileOps

from graphs.state import DocParseInput, DocParseOutput

logger = logging.getLogger(__name__)


def doc_parse_node(
    state: DocParseInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DocParseOutput:
    """
    title: 论文文档解析
    desc: 将上传的论文文件(PDF/Word/TXT等)解析为纯文本内容
    """
    ctx = runtime.context
    paper_file = state.paper_file

    # 检查是否上传了文件
    if paper_file is None:
        logger.warning("No paper file provided")
        return DocParseOutput(
            paper_content="",
            parse_error="未上传论文文件，请上传PDF/Word/TXT等格式的论文。"
        )

    # 使用FileOps提取文本内容
    try:
        extracted_text = FileOps.extract_text(paper_file)

        # 检查提取结果是否包含错误信息
        if extracted_text.startswith("[FileOps Error]") or extracted_text.startswith("[解析失败]"):
            logger.error(f"Document parsing failed: {extracted_text}")
            return DocParseOutput(
                paper_content="",
                parse_error=extracted_text
            )

        # 检查提取的文本是否为空
        if not extracted_text or not extracted_text.strip():
            logger.warning("Extracted text is empty")
            return DocParseOutput(
                paper_content="",
                parse_error="文档内容为空，请检查上传的文件是否正确。"
            )

        logger.info(f"Successfully extracted text, length: {len(extracted_text)}")

        return DocParseOutput(
            paper_content=extracted_text.strip(),
            parse_error=""
        )
    except Exception as e:
        logger.error(f"Unexpected error during document parsing: {e}")
        return DocParseOutput(
            paper_content="",
            parse_error=f"文档解析出现异常: {str(e)}"
        )
