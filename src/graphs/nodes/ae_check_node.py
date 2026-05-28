from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def ae_check_node(state: GlobalState) -> GlobalState:
    result = get_review_nodes().ae_check(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        se_result=state.get("se_result", {}),
        field_info=state.get("field_info", {}),
        reviewer_config=state.get("reviewer_config", {}),
    )
    return {
        "ae_result": result,
        "ae_decision": result.get("ae_decision", "SEND_FOR_REVIEW"),
        "stage_outputs": {"ae_check": result},
    }
