from __future__ import annotations

from src.graphs.state import GlobalState


def parse_fail_output_node(state: GlobalState) -> GlobalState:
    message = state.get("parse_error", "文档解析失败。")
    return {
        "final_decision": "REJECT",
        "decision_letter": message,
        "stage_outputs": {"parse_fail_output": {"message": message}},
    }
