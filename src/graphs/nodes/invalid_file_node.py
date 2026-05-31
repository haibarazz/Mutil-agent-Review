from __future__ import annotations

from src.graphs.state import GlobalState


def invalid_file_node(state: GlobalState) -> GlobalState:
    fallback = "The uploaded content is not an academic manuscript."
    if state.get("output_language", "zh") != "en":
        fallback = "上传内容不是学术论文。"
    message = state.get("intent_detail") or fallback
    return {
        "final_decision": "REJECT",
        "decision_letter": message,
        "stage_outputs": {"invalid_file": {"message": message}},
    }
