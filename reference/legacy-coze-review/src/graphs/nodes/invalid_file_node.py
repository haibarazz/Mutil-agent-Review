"""非论文文件提示节点 - v3.2 新增"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import InvalidFileInput, InvalidFileOutput


def invalid_file_node(
    state: InvalidFileInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> InvalidFileOutput:
    """
    title: 非论文文件提示
    desc: 当上传的文件不是支持的论文格式时，提示用户重新上传论文手稿
    """
    ctx = runtime.context
    detail = state.intent_detail or "请上传论文手稿"

    output = (
        f"📄 **{detail}**\n\n"
        "我们仅支持以下论文手稿格式：\n"
        "- **PDF** (.pdf)\n"
        "- **Word** (.doc, .docx)\n"
        "- **LaTeX** (.tex)\n\n"
        "请重新上传符合格式的论文手稿文件。"
    )

    return InvalidFileOutput(formatted_output=output)
