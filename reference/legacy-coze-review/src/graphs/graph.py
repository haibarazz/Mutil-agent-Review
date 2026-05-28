"""论文审稿系统主图编排 - v3.2 LLM内容审查+审稿模式选择"""
from langgraph.graph import StateGraph, END

from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput,
    ContentCheckDecisionInput,
    ParseCheckInput,
    ReviewModeDecisionInput,
    SEDecisionInput,
    AEDecisionInput,
)

# 导入节点函数
from graphs.nodes.doc_parse_node import doc_parse_node
from graphs.nodes.parse_fail_output_node import parse_fail_output_node
from graphs.nodes.content_check_node import content_check_node
from graphs.nodes.invalid_file_node import invalid_file_node
from graphs.nodes.journal_req_collector_node import journal_req_collector_node
from graphs.nodes.field_analyst_node import field_analyst_node
from graphs.nodes.se_check_node import se_check_node
from graphs.nodes.ae_check_node import ae_check_node
from graphs.nodes.review_dispatch_node import review_dispatch_node
from graphs.nodes.reviewer1_node import reviewer1_node
from graphs.nodes.reviewer2_node import reviewer2_node
from graphs.nodes.reviewer3_node import reviewer3_node
from graphs.nodes.devils_advocate_node import devils_advocate_node
from graphs.nodes.ae_final_node import ae_final_node
from graphs.nodes.desk_reject_output_node import desk_reject_output_node


# ===== 条件分支函数 =====

def check_content_type(state: ContentCheckDecisionInput) -> str:
    """
    title: 内容类型判断
    desc: 判断上传内容是否为学术论文
    """
    if state.intent == "VALID_PAPER":
        return "是论文"
    return "非论文内容"


def check_parse_result(state: ParseCheckInput) -> str:
    """判断文档解析是否成功"""
    if state.parse_error:
        return "解析失败"
    return "解析成功"


def route_after_field_analyst(state: ReviewModeDecisionInput) -> str:
    """
    title: 审稿模式路由
    desc: 根据用户选择的审稿模式决定后续路径：完整审稿走SE初审，快速审稿直接外审
    """
    if state.review_mode == "QUICK_REVIEW":
        return "直接外审"
    return "SE初审"


def route_after_se(state: SEDecisionInput) -> str:
    """SE初审后的路由"""
    if state.se_decision == "DESK_REJECT":
        return "桌拒"
    return "通过"


def route_after_ae(state: AEDecisionInput) -> str:
    """AE筛选后的路由"""
    if state.ae_decision == "DESK_REJECT":
        return "桌拒"
    return "送外审"


# ===== 构建主图 =====

builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node("doc_parse", doc_parse_node)
builder.add_node("parse_fail_output", parse_fail_output_node)
builder.add_node("content_check", content_check_node, metadata={"type": "agent", "llm_cfg": "config/content_check_llm_cfg.json"})
builder.add_node("invalid_file", invalid_file_node)
builder.add_node("journal_req_collector", journal_req_collector_node, metadata={"type": "agent", "llm_cfg": "config/journal_req_collector_llm_cfg.json"})
builder.add_node("field_analyst", field_analyst_node, metadata={"type": "agent", "llm_cfg": "config/field_analyst_llm_cfg.json"})
builder.add_node("se_check", se_check_node, metadata={"type": "agent", "llm_cfg": "config/se_check_llm_cfg.json"})
builder.add_node("ae_check", ae_check_node, metadata={"type": "agent", "llm_cfg": "config/ae_check_llm_cfg.json"})
builder.add_node("review_dispatch", review_dispatch_node)
builder.add_node("reviewer1", reviewer1_node, metadata={"type": "agent", "llm_cfg": "config/reviewer1_llm_cfg.json"})
builder.add_node("reviewer2", reviewer2_node, metadata={"type": "agent", "llm_cfg": "config/reviewer2_llm_cfg.json"})
builder.add_node("reviewer3", reviewer3_node, metadata={"type": "agent", "llm_cfg": "config/reviewer3_llm_cfg.json"})
builder.add_node("devils_advocate", devils_advocate_node, metadata={"type": "agent", "llm_cfg": "config/devils_advocate_llm_cfg.json"})
builder.add_node("ae_final", ae_final_node, metadata={"type": "agent", "llm_cfg": "config/ae_final_llm_cfg.json"})
builder.add_node("desk_reject_output", desk_reject_output_node)

# ===== 设置入口 =====
builder.set_entry_point("doc_parse")

# ===== 文档解析分支 =====
builder.add_conditional_edges(
    source="doc_parse",
    path=check_parse_result,
    path_map={
        "解析成功": "content_check",
        "解析失败": "parse_fail_output",
    }
)
builder.add_edge("parse_fail_output", END)

# ===== LLM内容审查分支 =====
builder.add_conditional_edges(
    source="content_check",
    path=check_content_type,
    path_map={
        "是论文": "journal_req_collector",
        "非论文内容": "invalid_file",
    }
)
builder.add_edge("invalid_file", END)

# ===== 期刊要求 → 领域分析 → 审稿模式路由 =====
builder.add_edge("journal_req_collector", "field_analyst")
builder.add_conditional_edges(
    source="field_analyst",
    path=route_after_field_analyst,
    path_map={
        "SE初审": "se_check",
        "直接外审": "review_dispatch",
    }
)

# ===== SE初审分支 (仅完整审稿模式走SE) =====
builder.add_conditional_edges(
    source="se_check",
    path=route_after_se,
    path_map={
        "桌拒": "desk_reject_output",
        "通过": "ae_check",
    }
)

# ===== AE筛选分支 =====
builder.add_conditional_edges(
    source="ae_check",
    path=route_after_ae,
    path_map={
        "桌拒": "desk_reject_output",
        "送外审": "review_dispatch",
    }
)

# ===== 审稿分发 → 4审稿人并行 =====
builder.add_edge("review_dispatch", "reviewer1")
builder.add_edge("review_dispatch", "reviewer2")
builder.add_edge("review_dispatch", "reviewer3")
builder.add_edge("review_dispatch", "devils_advocate")

# ===== 4审稿人并行汇聚 → AE终审 =====
builder.add_edge(["reviewer1", "reviewer2", "reviewer3", "devils_advocate"], "ae_final")

# ===== AE终审 → 结束 =====
builder.add_edge("ae_final", END)

# ===== 桌拒 → 结束 =====
builder.add_edge("desk_reject_output", END)

# ===== 编译图 =====
main_graph = builder.compile()
