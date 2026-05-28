from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def content_check_node(state: GlobalState) -> GlobalState:
    result = get_review_nodes().content_check(state["parsed_paper"])
    return {
        "content_check": result,
        "intent": result["intent"],
        "intent_detail": result.get("intent_detail", ""),
        "stage_outputs": {"content_check": result},
    }
