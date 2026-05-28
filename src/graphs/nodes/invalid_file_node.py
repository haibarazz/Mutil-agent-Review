from __future__ import annotations

from src.graphs.state import GlobalState


def invalid_file_node(state: GlobalState) -> GlobalState:
    message = state.get("intent_detail") or "上传内容不是学术论文。"
    return {
        "final_decision": "REJECT",
        "decision_letter": message,
        "stage_outputs": {"invalid_file": {"message": message}},
    }
