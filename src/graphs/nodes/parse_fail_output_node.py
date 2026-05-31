from __future__ import annotations

from src.graphs.state import GlobalState

# 解析失败的输出
def parse_fail_output_node(state: GlobalState) -> GlobalState:
    fallback = "Document parsing failed."
    if state.get("output_language", "zh") != "en":
        fallback = "文档解析失败。"
    message = state.get("parse_error", fallback)
    return {
        "final_decision": "REJECT",
        "decision_letter": message,
        "stage_outputs": {"parse_fail_output": {"message": message}},
    }
