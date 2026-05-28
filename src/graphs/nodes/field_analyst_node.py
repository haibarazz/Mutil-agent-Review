from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def field_analyst_node(state: GlobalState) -> GlobalState:
    result = get_review_nodes().field_analyst(state["parsed_paper"], state["journal_requirements"])
    return {
        "field_analysis": result,
        "field_info": result.get("field_info", {}),
        "reviewer_config": result.get("reviewer_config", {}),
        "stage_outputs": {"field_analysis": result},
    }
