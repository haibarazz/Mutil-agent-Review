from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def se_check_node(state: GlobalState) -> GlobalState:
    result = get_review_nodes().se_check(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        field_info=state.get("field_info", {}),
    )
    return {
        "se_result": result,
        "se_decision": result.get("se_decision", "PASS"),
        "stage_outputs": {"se_check": result},
    }
