from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graphs.nodes.ae_check_node import ae_check_node
from src.graphs.nodes.ae_final_node import ae_final_node
from src.graphs.nodes.content_check_node import content_check_node
from src.graphs.nodes.desk_reject_output_node import desk_reject_output_node
from src.graphs.nodes.devils_advocate_node import devils_advocate_node
from src.graphs.nodes.doc_parse_node import doc_parse_node
from src.graphs.nodes.field_analyst_node import field_analyst_node
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
    return "parse_failed" if state.get("parse_error") else "parse_ok"


def route_after_content_check(state: GlobalState) -> str:
    return "valid_paper" if state.get("intent") == "VALID_PAPER" else "not_paper"


def route_after_field_analyst(state: GlobalState) -> str:
    return "quick_review" if state.get("review_mode") == "QUICK_REVIEW" else "full_review"


def route_after_se(state: GlobalState) -> str:
    return "desk_reject" if state.get("se_decision") == "DESK_REJECT" else "pass"


def route_after_ae(state: GlobalState) -> str:
    return "desk_reject" if state.get("ae_decision") == "DESK_REJECT" else "send_for_review"


builder = StateGraph(GlobalState)

builder.add_node("doc_parse", doc_parse_node)
builder.add_node("parse_fail_output", parse_fail_output_node)
builder.add_node("content_check", content_check_node)
builder.add_node("invalid_file", invalid_file_node)
builder.add_node("journal_req_collector", journal_req_collector_node)
builder.add_node("field_analyst", field_analyst_node)
builder.add_node("se_check", se_check_node)
builder.add_node("ae_check", ae_check_node)
builder.add_node("review_dispatch", review_dispatch_node)
builder.add_node("reviewer1", reviewer1_node)
builder.add_node("reviewer2", reviewer2_node)
builder.add_node("reviewer3", reviewer3_node)
builder.add_node("devils_advocate", devils_advocate_node)
builder.add_node("ae_final", ae_final_node)
builder.add_node("desk_reject_output", desk_reject_output_node)

builder.set_entry_point("doc_parse")

builder.add_conditional_edges(
    "doc_parse",
    check_parse_result,
    {"parse_ok": "content_check", "parse_failed": "parse_fail_output"},
)
builder.add_edge("parse_fail_output", END)

builder.add_conditional_edges(
    "content_check",
    route_after_content_check,
    {"valid_paper": "journal_req_collector", "not_paper": "invalid_file"},
)
builder.add_edge("invalid_file", END)

builder.add_edge("journal_req_collector", "field_analyst")
builder.add_conditional_edges(
    "field_analyst",
    route_after_field_analyst,
    {"full_review": "se_check", "quick_review": "review_dispatch"},
)

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
builder.add_edge("desk_reject_output", END)

builder.add_edge("review_dispatch", "reviewer1")
builder.add_edge("review_dispatch", "reviewer2")
builder.add_edge("review_dispatch", "reviewer3")
builder.add_edge("review_dispatch", "devils_advocate")
builder.add_edge(["reviewer1", "reviewer2", "reviewer3", "devils_advocate"], "ae_final")
builder.add_edge("ae_final", END)

main_graph = builder.compile()
