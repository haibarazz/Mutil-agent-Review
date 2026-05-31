from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def devils_advocate_node(state: GlobalState) -> GlobalState:
    report = get_review_nodes().devils_advocate(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        ae_result=state.get("ae_result", {}),
        output_language=state.get("output_language", "zh"),
    )
    return {
        "reviewer_reports": [report],
        "stage_outputs": {"devils_advocate": report},
    }
