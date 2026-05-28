from __future__ import annotations

from src.graphs.review_nodes import default_quick_review_ae_result
from src.graphs.state import GlobalState


def review_dispatch_node(state: GlobalState) -> GlobalState:
    if "ae_result" in state:
        return {"stage_outputs": {"review_dispatch": {"mode": "with_ae_context"}}}
    ae_result = default_quick_review_ae_result()
    return {
        "ae_result": ae_result,
        "ae_decision": "SEND_FOR_REVIEW",
        "stage_outputs": {
            "ae_check": ae_result,
            "review_dispatch": {"mode": "quick_review_default_context"},
        },
    }
