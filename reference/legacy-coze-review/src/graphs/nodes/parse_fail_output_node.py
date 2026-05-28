"""解析失败输出节点 - v3.0 文档解析失败时输出友好提示，修复P0"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import ParseFailInput, ParseFailOutput


def parse_fail_output_node(
    state: ParseFailInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ParseFailOutput:
    """
    title: 解析失败提示
    desc: 文档解析失败时输出友好的错误提示，终止流程
    """
    ctx = runtime.context

    output = f"""# ❌ 文档解析失败

---

很抱歉，您上传的论文文件无法被正确解析。

**错误信息**: {state.parse_error}

---

## 可能的原因和解决方案

1. **文件格式不支持** → 请上传 PDF、Word(docx)、TXT 或 Markdown 格式的文件
2. **文件损坏** → 请检查文件是否完整，尝试重新导出或下载
3. **文件为空** → 请确认文件中包含内容
4. **文件过大** → 请尝试上传较小的文件

---

💡 *请修正后重新上传文件，我们将立即为您进行审稿。*
"""

    return ParseFailOutput(formatted_output=output)
