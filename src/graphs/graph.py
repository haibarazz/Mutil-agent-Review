from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graphs.node_diagnostics import with_node_diagnostics
from src.graphs.nodes.ae_check_node import ae_check_node
from src.graphs.nodes.ae_final_node import ae_final_node
from src.graphs.nodes.content_check_node import content_check_node
from src.graphs.nodes.desk_reject_output_node import desk_reject_output_node
from src.graphs.nodes.devils_advocate_node import devils_advocate_node
from src.graphs.nodes.doc_parse_node import doc_parse_node
from src.graphs.nodes.field_analyst_node import field_analyst_node
from src.graphs.nodes.final_artifact_render_node import final_artifact_render_node
from src.graphs.nodes.invalid_file_node import invalid_file_node
from src.graphs.nodes.journal_req_collector_node import journal_req_collector_node
from src.graphs.nodes.parse_fail_output_node import parse_fail_output_node
from src.graphs.nodes.review_dispatch_node import review_dispatch_node
from src.graphs.nodes.reviewer1_node import reviewer1_node
from src.graphs.nodes.reviewer2_node import reviewer2_node
from src.graphs.nodes.reviewer3_node import reviewer3_node
from src.graphs.nodes.se_check_node import se_check_node
from src.graphs.state import GlobalState


def check_parse_result(state: GlobalState) -> str:
    # 文档解析后路由：解析失败就直接结束，解析成功才进入内容审查。
    return "parse_failed" if state.get("parse_error") else "parse_ok"


def route_after_content_check(state: GlobalState) -> str:
    # 内容审查后路由：只有像学术论文的内容才继续审稿。
    return "valid_paper" if state.get("intent") == "VALID_PAPER" else "not_paper"


def route_after_field_analyst(state: GlobalState) -> str:
    # 领域分析后路由：快速审稿跳过编辑初筛，完整审稿进入 SE 初筛。
    return "quick_review" if state.get("review_mode") == "QUICK_REVIEW" else "full_review"


def route_after_se(state: GlobalState) -> str:
    # SE 初筛后路由：桌拒直接输出拒稿意见，通过则交给 AE。
    return "desk_reject" if state.get("se_decision") == "DESK_REJECT" else "pass"


def route_after_ae(state: GlobalState) -> str:
    # AE 筛选后路由：桌拒直接输出，通过则进入外审分发。
    return "desk_reject" if state.get("ae_decision") == "DESK_REJECT" else "send_for_review"


builder = StateGraph(GlobalState)


def add_diagnosed_node(name: str, node_func) -> None:
    # 所有节点统一套一层诊断包装，异常时能知道是哪个 LangGraph 节点失败。
    builder.add_node(name, with_node_diagnostics(name, node_func))

# doc_parse: 第一个节点，把上传的 PDF/MD/TEX/DOCX 解析成统一的 ParsedPaper。
add_diagnosed_node("doc_parse", doc_parse_node)
# parse_fail_output: 解析失败时生成面向用户的失败说明。
add_diagnosed_node("parse_fail_output", parse_fail_output_node)
# content_check: 用 LLM 判断上传内容是否真的是学术论文。
add_diagnosed_node("content_check", content_check_node)
# invalid_file: 内容不是论文时，提示用户重新上传有效论文。
add_diagnosed_node("invalid_file", invalid_file_node)
# journal_req_collector: 从 venue md 加载官方投稿要求和智能体 venue profile。
add_diagnosed_node("journal_req_collector", journal_req_collector_node)
# field_analyst: 分析论文领域、研究范式，并生成审稿人配置。
add_diagnosed_node("field_analyst", field_analyst_node)
# se_check: Senior Editor 初筛，判断是否应该桌拒。
add_diagnosed_node("se_check", se_check_node)
# ae_check: Associate Editor 二次筛选，生成外审关注点和论文 rubric。
add_diagnosed_node("ae_check", ae_check_node)
# review_dispatch: 虚拟分发节点，把同一份状态分发给多个并行审稿人。
add_diagnosed_node("review_dispatch", review_dispatch_node)
# reviewer1: 方法论审稿人，重点看方法、实验、对照和可复现性。
add_diagnosed_node("reviewer1", reviewer1_node)
# reviewer2: 领域审稿人，重点看学术贡献、相关工作和领域定位。
add_diagnosed_node("reviewer2", reviewer2_node)
# reviewer3: 跨学科审稿人，重点看表达、假设、适用性和读者理解成本。
add_diagnosed_node("reviewer3", reviewer3_node)
# devils_advocate: 反方辩护人，专门攻击论文最强主张和潜在逻辑漏洞。
add_diagnosed_node("devils_advocate", devils_advocate_node)
# ae_final: AE 终审，综合所有审稿意见生成最终决定和返修路线。
add_diagnosed_node("ae_final", ae_final_node)
# desk_reject_output: SE/AE 桌拒时生成正式拒稿说明和改进建议。
add_diagnosed_node("desk_reject_output", desk_reject_output_node)
# final_artifact_render: 统一把完整审稿、桌拒、无效输入等路径渲染成最终报告。
add_diagnosed_node("final_artifact_render", final_artifact_render_node)

# LangGraph 从文档解析开始。
builder.set_entry_point("doc_parse")

# 解析失败不再继续跑 LLM，避免无效内容进入后续审稿。
builder.add_conditional_edges(
    "doc_parse",
    check_parse_result,
    {"parse_ok": "content_check", "parse_failed": "parse_fail_output"},
)
builder.add_edge("parse_fail_output", "final_artifact_render")

# 内容不像论文时直接结束，避免把任意文件当论文审。
builder.add_conditional_edges(
    "content_check",
    route_after_content_check,
    {"valid_paper": "journal_req_collector", "not_paper": "invalid_file"},
)
builder.add_edge("invalid_file", "final_artifact_render")

# 收集完期刊要求后，先做领域分析，再根据审稿模式分流。
builder.add_edge("journal_req_collector", "field_analyst")
builder.add_conditional_edges(
    "field_analyst",
    route_after_field_analyst,
    {"full_review": "se_check", "quick_review": "review_dispatch"},
)

# 完整审稿先走 SE，再走 AE；任一环节桌拒都会进入桌拒输出。
builder.add_conditional_edges(
    "se_check",
    route_after_se,
    {"pass": "ae_check", "desk_reject": "desk_reject_output"},
)
builder.add_conditional_edges(
    "ae_check",
    route_after_ae,
    {"send_for_review": "review_dispatch", "desk_reject": "desk_reject_output"},
)
builder.add_edge("desk_reject_output", "final_artifact_render")

# 外审阶段四路并行：三个审稿人 + 一个反方辩护人。
builder.add_edge("review_dispatch", "reviewer1")
builder.add_edge("review_dispatch", "reviewer2")
builder.add_edge("review_dispatch", "reviewer3")
builder.add_edge("review_dispatch", "devils_advocate")
# 四路审稿全部完成后汇总到 AE 终审。
builder.add_edge(["reviewer1", "reviewer2", "reviewer3", "devils_advocate"], "ae_final")
# 所有终止路径最后都进入统一渲染节点，service 只负责把内容写成文件。
builder.add_edge("ae_final", "final_artifact_render")
builder.add_edge("final_artifact_render", END)

# 编译后的 main_graph 是 CLI/API 实际调用的 LangGraph 对象。
main_graph = builder.compile()
