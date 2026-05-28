"""审稿分发节点 - v3.0 虚拟分发节点，将AE筛选结果透传给4个并行审稿人"""
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import ReviewDispatchInput, ReviewDispatchOutput


def review_dispatch_node(
    state: ReviewDispatchInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ReviewDispatchOutput:
    """
    title: 审稿分发
    desc: 虚拟分发节点，将AE筛选结果透传给4个并行审稿人
    """
    return ReviewDispatchOutput(
        paper_content=state.paper_content,
        journal_requirements=state.journal_requirements,
        ae_assessment=state.ae_assessment,
        review_focus_points=state.review_focus_points,
        paper_rubric=state.paper_rubric,
        reviewer_config=state.reviewer_config,
    )
