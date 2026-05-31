from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def ae_final_node(state: GlobalState) -> GlobalState:
    result = get_review_nodes().ae_final(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        ae_result=state.get("ae_result", {}),
        reviewer_reports=state.get("reviewer_reports", []),
        output_language=state.get("output_language", "zh"),
    )
    return {
        "ae_final": result,
        "final_decision": result.get("final_decision", "MAJOR_REVISION"),
        "decision_letter": result.get("decision_letter", ""),
        "stage_outputs": {"ae_final": result},
    }
