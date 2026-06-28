from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def ae_decision_node(state: GlobalState) -> GlobalState:
    """AE 裁决节点：只判断最终决定，不写决定信和返修路线。"""
    result = get_review_nodes().ae_decision(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        ae_result=state.get("ae_result", {}),
        reviewer_reports=state.get("reviewer_reports", []),
        output_language=state.get("output_language", "zh"),
    )
    return {
        "ae_decision_result": result,
        "stage_outputs": {"ae_decision": result},
    }
