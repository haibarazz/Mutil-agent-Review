from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def ae_report_node(state: GlobalState) -> GlobalState:
    """AE 报告节点：基于已冻结的裁决写作者反馈，不重新做决定。"""
    result = get_review_nodes().ae_report(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        ae_result=state.get("ae_result", {}),
        ae_decision=state["ae_decision_result"],
        reviewer_reports=state.get("reviewer_reports", []),
        output_language=state.get("output_language", "zh"),
    )
    return {
        "ae_report": result,
        "stage_outputs": {"ae_report": result},
    }
